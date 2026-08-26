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
from typing import Any

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
    params: list = []


# --- method handlers -------------------------------------------------------
# each handler receives (data: Web3Body) and returns the JSON-RPC "result"

def _resolveBlockNumber(_blockParam):
    """Translate a JSON-RPC block parameter ('latest', hex height, int, ...)
    into an integer block height.

    Raises _RpcError(-32602 invalid params) on malformed input so the client
    gets a real JSON-RPC error instead of a swallowed null.
    """
    _chain = node.state.beaconChain
    if isinstance(_blockParam, str):
        if _blockParam in ("latest", "pending", "safe", "finalized"):
            return len(_chain.blocks) - 1
        elif _blockParam == "earliest":
            return 0
        _s = _blockParam[2:] if _blockParam.startswith("0x") else _blockParam
        try:
            return int(_s, 16)
        except ValueError:
            raise _RpcError({"code": -32602,
                              "message": f"Invalid block param: {_blockParam}"})
    return _blockParam


def eth_getBalance(data):
    return hex(int((node.state.getAccount(w3.toChecksumAddress(data.params[0]), True).balance)))


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
    return hex(len(node.state.getAccount(w3.toChecksumAddress(data.params[0]), True).sent))


def eth_getCode(data):
    return f"0x{node.state.getAccount(data.params[0], True).code.hex()}"


def _execCall(data):
    """Run an eth_Call and return the CallEnv, raising a spec-compliant
    code:3 "execution reverted" error if the call reverted.

    Per the execution-apis spec, both eth_call and eth_estimateGas must
    return error code 3 with the raw EVM revert data on revert.
    """
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
    return node.integrateETHTransaction(data.params[0])


def eth_getTransactionReceipt(data):
    return node.txReceipt(data.params[0])


def eth_getStorageAt(data):
    _slot = data.params[1]
    if isinstance(_slot, str):
        _slot = _slot[2:] if _slot.startswith("0x") else _slot
        _slot = int(_slot, 16)
    return hex(int(node.state.getAccount(data.params[0], True).storage[int(_slot)]))


def eth_getTransactionByHash(data):
    return node.ethGetTransactionByHash(data.params[0])


def _syntheticTxBlock(txDict, blockNumber):
    """Build a single-transaction synthetic "block" from a stored transaction.

    Beacon blocks don't map 1:1 to Ethereum blocks: transactions can be valid
    and broadcast without a beacon block being mined. Since eth_blockNumber
    reports the transaction count, blocks are synthesized from the global tx
    order so that every "height" resolves to exactly one transaction.
    """
    _tx = Transaction(txDict)
    return {
        # synthetic block hash = canonical type-0 (legacy) tx hash
        "hash": "0x" + _tx.txid if not _tx.txid.startswith("0x") else _tx.txid,
        "parentHash": "0x" + ("0" * 64) if blockNumber == 0 else None,
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
        "transactionsRoot": "0x" + _tx.txid,
        "stateRoot": ("0x" + node.state.hash) if node.state.hash else "0x" + "0" * 64,
        "receiptsRoot": "0x" + _tx.txid,
        "uncles": [],
        "transactions": [_tx.web3Returnable()],
    }


def eth_getBlockByNumber(data):
    _blockTx = data.params[1] if len(data.params) > 1 else False
    _blockNumber = _resolveBlockNumber(data.params[0])
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
    # type-0 (raptor) hash; if the client sent a type-2 (eth) hash, resolve
    # it via the type2ToType0Hash alias map (O(1) dict lookup).
    _hashes = node.store.getTxHashes()
    try:
        _index = _hashes.index(_hash)
    except ValueError:
        _alias = node.state.type2ToType0Hash.get(_hash)
        if _alias is None:
            return None
        try:
            _index = _hashes.index(_alias)
        except ValueError:
            return None
    result = _syntheticTxBlock(_tx, _index)
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

    @app.post("/web3")
    def handleWeb3Request(data: Web3Body):
        _begin = time.time()

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
        _resp = json.dumps(_respdict)
        if node.state.verbose:
            print(f"{data.method} request completed in {round((time.time() - _begin) * 1000, 3)}ms")
            print(f"Response : {_resp}")
        return fastapi.Response(content=_resp, media_type='application/json')

    return handleWeb3Request
