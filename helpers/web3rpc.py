"""
Web3-compatible JSON-RPC endpoint (POST /web3).

Handles Ethereum-style JSON-RPC methods (eth_getBalance, eth_call, ...) so
web3 wallets such as MetaMask can talk to a RaptorChain node.

The node instance is injected at startup via `registerNode()` / `createRouter()`
to avoid circular imports with RaptorChain.py.
"""

import inspect

# fixes a compatibility issue (different function names across versions)
# (same shim as in RaptorChain.py - needed here because this module imports
# web3 directly)
if not hasattr(inspect, "getargspec"):
    inspect.getargspec = inspect.getfullargspec

import json
import time
from typing import Any, List, Union

import fastapi
import pydantic
from web3.auto import w3

from helpers.datatypes import Transaction
from .utils import printError

# set by registerNode() before the server starts serving requests
node = None


def registerNode(_node):
    """Inject the running Node instance (called once from RaptorChain.py)."""
    global node
    node = _node


class Web3Body(pydantic.BaseModel):
    id: Any = None
    method: str
    params: list = pydantic.Field(default_factory=list)


# --- param validation helpers ----------------------------------------------
# Raise _RpcError(-32602 invalid params) so clients get a spec-compliant
# error instead of an opaque -32603 internal error from IndexError/TypeError.
# _RpcError is defined further down; these are only called at runtime so the
# forward reference resolves fine.

def _requireParams(data, n):
    """Ensure data.params has at least n entries, else raise -32602."""
    if len(data.params) < n:
        raise _RpcError({"code": -32602,
                         "message": f"Invalid params: {data.method} requires {n} argument(s), got {len(data.params)}"})

def _requireAddress(s):
    """Validate and checksum an Ethereum address, else raise -32602."""
    if not isinstance(s, str):
        raise _RpcError({"code": -32602, "message": f"Invalid address: {s!r}"})
    try:
        return w3.to_checksum_address(s)
    except Exception:
        raise _RpcError({"code": -32602, "message": f"Invalid address: {s}"})

def _requireHash(s):
    """Validate a 0x-prefixed hash string, else raise -32602."""
    if not isinstance(s, str) or not s.startswith("0x"):
        raise _RpcError({"code": -32602, "message": f"Invalid hash: {s!r}"})
    return s


# --- method handlers -------------------------------------------------------
# each handler receives (data: Web3Body) and returns the JSON-RPC "result"

def _resolveBlockNumber(_blockParam):
    """Translate a JSON-RPC block parameter ('latest', hex height, int, ...)
    into an integer block height.

    Uses the transaction-store height (txCount - 1) for 'latest' so that it
    stays consistent with eth_blockNumber, which also reports txCount - 1.
    The synthetic blocks served by eth_getBlockByNumber are keyed on the tx
    order, so 'latest' must resolve to the last tx index, not the beacon
    block count (which can diverge).

    Raises _RpcError(-32602 invalid params) on malformed input so the client
    gets a real JSON-RPC error instead of a swallowed null.
    """
    if isinstance(_blockParam, str):
        if _blockParam in ("latest", "pending", "safe", "finalized"):
            return max(node.store.txCount() - 1, 0)
        elif _blockParam == "earliest":
            return 0
        _s = _blockParam[2:] if _blockParam.startswith("0x") else _blockParam
        try:
            return int(_s, 16)
        except ValueError:
            raise _RpcError({"code": -32602,
                              "message": f"Invalid block param: {_blockParam}"})
    # numeric block height passed directly (reject bool/None/dict/float)
    if isinstance(_blockParam, int) and not isinstance(_blockParam, bool):
        return _blockParam
    raise _RpcError({"code": -32602, "message": f"Invalid block param: {_blockParam!r}"})


def eth_getBalance(data):
    _requireParams(data, 1)
    _acct = node.state.getAccount(_requireAddress(data.params[0]), True)
    return hex(int(_acct.balance or 0))


def net_version(data):
    return str(node.state.chainID)


def eth_coinbase(data):
    return node.state.beaconChain.getLastBeacon().miner


def eth_mining(data):
    return False


def eth_gasPrice(data):
    return hex(node.state.gasPrice)


def eth_blockNumber(data):
    return hex(max(node.store.txCount() - 1, 0))


def eth_getTransactionCount(data):
    _requireParams(data, 1)
    return hex(len(node.state.getAccount(_requireAddress(data.params[0]), True).sent))


def eth_getCode(data):
    _requireParams(data, 1)
    _code = node.state.getAccount(_requireAddress(data.params[0]), True).code
    # guard against None (uninitialized account) — Ethereum returns "0x"
    return f"0x{_code.hex()}" if _code is not None else "0x"


def _execCall(data):
    """Run an eth_Call and return the CallEnv, raising a spec-compliant
    code:3 "execution reverted" error if the call reverted.

    Per the execution-apis spec, both eth_call and eth_estimateGas must
    return error code 3 with the raw EVM revert data on revert.
    """
    _requireParams(data, 1)
    _env = node.state.eth_Call(data.params[0])
    if not _env.getSuccess():
        raise _RpcError({"code": 3, "message": "execution reverted",
                         "data": "0x" + _env.returnValue.hex()})
    return _env


def eth_estimateGas(data):
    return hex(_execCall(data).gasUsed)


def eth_call(data):
    return f"0x{_execCall(data).returnValue.hex()}"


def eth_getCompilers(data):
    return []


def eth_sendRawTransaction(data):
    _requireParams(data, 1)
    _txid = node.integrateETHTransaction(data.params[0])
    # Verify the transaction was actually accepted by the store.
    # integrateETHTransaction always returns a computed hash regardless of
    # whether checkTxs accepted the tx; a rejected tx would otherwise return
    # a hash that doesn't correspond to any stored transaction.
    if not node.store.hasTransaction(_txid):
        raise _RpcError({"code": -32000, "message": "Transaction rejected"})
    return _txid


def eth_getTransactionReceipt(data):
    _requireParams(data, 1)
    return node.txReceipt(data.params[0])


def eth_getStorageAt(data):
    _requireParams(data, 2)
    _slot = data.params[1]
    if isinstance(_slot, str):
        _s = _slot[2:] if _slot.startswith("0x") else _slot
        try:
            _slot = int(_s, 16)
        except ValueError:
            raise _RpcError({"code": -32602, "message": f"Invalid storage slot: {data.params[1]}"})
    elif not isinstance(_slot, int) or isinstance(_slot, bool):
        raise _RpcError({"code": -32602, "message": f"Invalid storage slot: {_slot!r}"})
    # Ethereum returns 0x0 for unset storage slots, not an error.
    return hex(int(node.state.getAccount(_requireAddress(data.params[0]), True).storage.get(int(_slot), 0)))


def eth_getTransactionByHash(data):
    _requireParams(data, 1)
    return node.ethGetTransactionByHash(data.params[0])


def _syntheticTxBlock(txDict, blockNumber, parentHash=None):
    """Build a single-transaction synthetic "block" from a stored transaction.

    Beacon blocks don't map 1:1 to Ethereum blocks: transactions can be valid
    and broadcast without a beacon block being mined. Since eth_blockNumber
    reports the transaction count, blocks are synthesized from the global tx
    order so that every "height" resolves to exactly one transaction.

    parentHash may be passed by callers that already hold the ordered hash
    list (e.g. eth_getBlockByHash) to avoid a second O(n) copy; otherwise it
    is resolved from the store.
    """
    _tx = Transaction(txDict)
    # parentHash: zero for genesis, otherwise the previous tx's hash in order.
    if blockNumber == 0:
        _parentHash = "0x" + "0" * 64
    elif parentHash is not None:
        _parentHash = parentHash
    else:
        _hashes = node.store.getTxHashes()
        _parentHash = _hashes[blockNumber - 1] if 0 <= blockNumber - 1 < len(_hashes) else "0x" + "0" * 64
    # stateRoot: node.state.hash is HexBytes after calcStateRoot(), "" before.
    # Guard against both str and bytes to avoid TypeError on concatenation.
    _stateHash = node.state.hash
    if _stateHash:
        _stateRoot = _stateHash.hex() if hasattr(_stateHash, "hex") else str(_stateHash)
        if not _stateRoot.startswith("0x"):
            _stateRoot = "0x" + _stateRoot
    else:
        _stateRoot = "0x" + "0" * 64
    # txid from w3.solidityKeccak().hex() is always 0x-prefixed; avoid double.
    _txid = _tx.txid if _tx.txid.startswith("0x") else "0x" + _tx.txid
    return {
        # synthetic block hash = canonical type-0 (legacy) tx hash
        "hash": _txid,
        "parentHash": _parentHash,
        "number": hex(blockNumber),
        "difficulty": hex(node.state.beaconChain.difficulty),
        "totalDifficulty": hex(node.state.beaconChain.difficulty),
        "extraData": "0x",
        "gasLimit": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "gasUsed": hex(_tx.gasUsed),
        "logsBloom": "0x" + bytes(_tx.logsBloom).hex(),
        "miner": _tx.sender,
        "mixHash": "0x" + ("0" * 64),
        "nonce": "0x0000000000000000",
        "sha3Uncles": "0x" + ("0" * 64),
        "size": "0x0",
        "timestamp": hex(int(_tx.timestamp or 0)),
        "transactionsRoot": _txid,
        "stateRoot": _stateRoot,
        "receiptsRoot": _txid,
        "uncles": [],
        "transactions": [_tx.web3Returnable()],
    }


def eth_getBlockByNumber(data):
    _requireParams(data, 1)
    _blockTx = data.params[1] if len(data.params) > 1 else False
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    _count = node.store.txCount()
    if _blockNumber < 0 or _blockNumber >= _count:
        return None
    _txs = node.store.getTxsByRange(_blockNumber, _blockNumber + 1)
    if not _txs or _txs[0] is None:
        return None
    result = _syntheticTxBlock(_txs[0], _blockNumber)
    if not _blockTx:  # hashes only
        result["transactions"] = [result["transactions"][0]["hash"]]
    return result


def eth_getBlockByHash(data):
    _requireParams(data, 1)
    _hash = data.params[0]
    _fullTx = data.params[1] if len(data.params) > 1 else False
    # beacon proofs still resolve to real beacon blocks
    _block = node.state.beaconChain.blocksByHash.get(_hash)
    if _block is not None:
        result = _block.web3Returnable()
        if _fullTx:  # fetch transactions as well
            result["transactions"] = [node.ethGetTransactionByHash(_txid) for _txid in result["transactions"]]
        return result
    # otherwise treat the hash as a transaction hash -> synthetic block
    _tx = node.getTransaction(_hash)
    if not _tx:
        return None
    # Look up the tx's position in the ordered list.  txsOrder stores the
    # type-0 (raptor) hash; node.getTransaction already resolved any type-2
    # (eth) alias above, so we just need the type-0 hash to index into
    # txsOrder.  Resolve it once via the alias map (O(1) dict lookup).
    _type0Hash = node.state.type2ToType0Hash.get(_hash, _hash)
    _hashes = node.store.getTxHashes()
    try:
        _index = _hashes.index(_type0Hash)
    except ValueError:
        return None
    result = _syntheticTxBlock(_tx, _index,
                               parentHash=(_hashes[_index - 1] if _index > 0 else None))
    if not _fullTx:  # hashes only
        result["transactions"] = [result["transactions"][0]["hash"]]
    return result


# JSON-RPC 2.0 error codes
ERR_METHOD_NOT_FOUND = {"code": -32601, "message": "Method not found"}


class _RpcError(Exception):
    """Carries a JSON-RPC 2.0 error object to the dispatcher."""
    def __init__(self, errorObj):
        self.errorObj = errorObj


def _methodNotFound(data):
    # signal to the dispatcher that this is an error, not a result
    raise _RpcError(ERR_METHOD_NOT_FOUND)


DEFAULT_RESULT = _methodNotFound

METHODS = {
    "eth_getBalance": eth_getBalance,
    "net_version": net_version,
    "eth_coinbase": eth_coinbase,
    "eth_mining": eth_mining,
    "eth_gasPrice": eth_gasPrice,
    "eth_blockNumber": eth_blockNumber,
    "eth_getTransactionCount": eth_getTransactionCount,
    "eth_getCode": eth_getCode,
    "eth_estimateGas": eth_estimateGas,
    "eth_call": eth_call,
    "eth_getCompilers": eth_getCompilers,
    "eth_sendRawTransaction": eth_sendRawTransaction,
    "eth_getTransactionReceipt": eth_getTransactionReceipt,
    "eth_getStorageAt": eth_getStorageAt,
    "eth_getTransactionByHash": eth_getTransactionByHash,
    "eth_getBlockByNumber": eth_getBlockByNumber,
    "eth_getBlockByHash": eth_getBlockByHash,
    "eth_chainId": lambda data: hex(node.state.chainID),
}


# --- HTTP entry point ------------------------------------------------------

def createRouter(app: fastapi.FastAPI):
    """Attach the POST /web3 route to the given FastAPI app."""

    def _handleSingle(data: Web3Body):
        """Process one JSON-RPC request.

        Returns the response dict, or None when the request is a notification
        (no id) so the caller can omit it from the HTTP response per spec.
        """
        _begin = time.time()

        if node is None:
            _respdict = {"id": data.id, "jsonrpc": "2.0",
                         "error": {"code": -32000, "message": "Node not ready"}}
            return None if data.id is None else _respdict

        if node.state.verbose:
            print(f"/web3 POST received, data : {data}")

        handler = METHODS.get(data.method, DEFAULT_RESULT)
        try:
            result = handler(data)
            _respdict = {"id": data.id, "jsonrpc": "2.0", "result": result}
        except _RpcError as e:
            _respdict = {"id": data.id, "jsonrpc": "2.0", "error": e.errorObj}
            if node.state.verbose:
                printError(f"web3 RPC error on {data.method}: {e.errorObj}")
        except Exception as e:
            _respdict = {"id": data.id, "jsonrpc": "2.0",
                         "error": {"code": -32603, "message": f"Internal error: {e.__repr__()}"}}
            if node.state.verbose:
                printError(f"web3 RPC error on {data.method}: {e.__repr__()}")
        if node.state.verbose:
            print(f"{data.method} request completed in {round((time.time() - _begin) * 1000, 3)}ms")
            print(f"Response : {json.dumps(_respdict)}")
        # JSON-RPC 2.0: a request without an id is a notification → no response.
        return None if data.id is None else _respdict

    @app.post("/web3")
    def handleWeb3Request(data: Union[Web3Body, List[Web3Body]]):
        # Batch request: a JSON array of requests → array of responses.
        # Notifications (no id) are processed but omitted from the response.
        if isinstance(data, list):
            _responses = []
            for _item in data:
                _r = _handleSingle(_item)
                if _r is not None:
                    _responses.append(_r)
            return fastapi.Response(content=json.dumps(_responses),
                                    media_type='application/json')
        # Single request
        _respdict = _handleSingle(data)
        if _respdict is None:
            # notification — no content
            return fastapi.Response(status_code=204)
        _resp = json.dumps(_respdict)
        return fastapi.Response(content=_resp, media_type='application/json')

    return handleWeb3Request
