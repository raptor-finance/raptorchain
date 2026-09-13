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
    # NOTE: eth_call is a READ — it intentionally does not persist anything.
    # During execution the EVM may create uninitialized Account objects for
    # the addresses it touches (see State.eth_Call); those are kept in memory
    # as a read cache (nothing is written to the store or the state root until
    # a real transaction commits).  They are never persisted, but they do grow
    # State.accounts, so under high-volume call traffic an LRU eviction would
    # bound that cache (tracked as A2).
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


# --- read-only convenience methods -------------------------------------------
# These are the lightweight, always-truthful responses wallets/ethers.js probe
# on startup and around eth_call.  None of them fabricate data: where the node
# has no real value to give (accounts, uncles, fee history) it returns the
# honest empty/identity value the spec expects, so clients don't choke.

def eth_syncing(data):
    """This node is never "syncing" in the geth sense — it is always serving.
    Spec allows a plain boolean False."""
    return False


def eth_accounts(data):
    """No unlocked accounts are held server-side."""
    return []


def web3_clientVersion(data):
    """Identity string for user-agents / client detection."""
    return f"RaptorChain/{node.state.version}"


def _txIndexForHash(_hash):
    """Resolve a tx/block hash to its index in the global tx order.

    Returns None when the hash is neither a stored transaction (any type) nor
    a beacon block hash.  Mirrors the resolution eth_getBlockByHash uses.
    """
    # beacon proofs resolve to real beacon blocks, which are NOT part of the
    # synthetic tx-index numbering — return None so callers treat them as
    # "not a tx-indexed block"
    if node.state.beaconChain.blocksByHash.get(_hash) is not None:
        return None
    _type0Hash = node.state.type2ToType0Hash.get(_hash, _hash)
    _hashes = node.store.getTxHashes()
    try:
        return _hashes.index(_type0Hash)
    except ValueError:
        return None


def eth_getBlockTransactionCountByNumber(data):
    _requireParams(data, 1)
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    _count = node.store.txCount()
    if _blockNumber < 0 or _blockNumber >= _count:
        return None
    _txs = node.store.getTxsByRange(_blockNumber, _blockNumber + 1)
    if not _txs or _txs[0] is None:
        return None
    return hex(len(_syntheticTxBlock(_txs[0], _blockNumber)["transactions"]))


def eth_getBlockTransactionCountByHash(data):
    _requireParams(data, 1)
    _hash = data.params[0]
    # beacon proofs still resolve to real beacon blocks
    _block = node.state.beaconChain.blocksByHash.get(_hash)
    if _block is not None:
        return hex(len(_block.web3Returnable()["transactions"]))
    _index = _txIndexForHash(_hash)
    if _index is None:
        return None
    _txs = node.store.getTxsByRange(_index, _index + 1)
    if not _txs or _txs[0] is None:
        return None
    return hex(len(_syntheticTxBlock(_txs[0], _index)["transactions"]))


def eth_getTransactionByBlockNumberAndIndex(data):
    """Return the transaction at the given index of a synthetic block.

    Synthetic blocks always contain exactly one transaction, so index 0
    returns that transaction and any other index returns null.  Beacon-block
    hashes are not part of the tx-index numbering and return null.
    """
    _requireParams(data, 2)
    _index = data.params[1]
    try:
        _index = int(_index, 16) if isinstance(_index, str) else int(_index)
    except (TypeError, ValueError):
        raise _RpcError({"code": -32602, "message": f"Invalid transaction index: {data.params[1]!r}"})
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    _count = node.store.txCount()
    if _blockNumber < 0 or _blockNumber >= _count:
        return None
    if _index != 0:
        return None
    _txs = node.store.getTxsByRange(_blockNumber, _blockNumber + 1)
    if not _txs or _txs[0] is None:
        return None
    return _syntheticTxBlock(_txs[0], _blockNumber)["transactions"][0]


def eth_getUncleCountByBlockHash(data):
    _requireParams(data, 1)
    if node.state.beaconChain.blocksByHash.get(data.params[0]) is None \
            and _txIndexForHash(data.params[0]) is None:
        return None
    return "0x0"


def eth_getUncleCountByBlockNumber(data):
    _requireParams(data, 1)
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    if _blockNumber < 0 or _blockNumber >= node.store.txCount():
        return None
    return "0x0"


def eth_feeHistory(data):
    """A minimal but spec-valid shape.

    Fabricating per-block base fees or gas-used ratios would be a lie — there
    is no base-fee market on RaptorChain.  The empty-but-valid response keeps
    ethers/viem from choking on fee estimation without inventing data.
    """
    _requireParams(data, 2)
    # validate block param the same way the other handlers do, so a malformed
    # "newestBlock" still yields a spec-compliant -32602
    _resolveBlockNumber(data.params[1])
    _blockCount = data.params[0]
    if isinstance(_blockCount, str):
        try:
            _blockCount = int(_blockCount, 16) if _blockCount.startswith("0x") else int(_blockCount)
        except ValueError:
            raise _RpcError({"code": -32602, "message": f"Invalid block count: {data.params[0]}"})
    if not isinstance(_blockCount, int) or isinstance(_blockCount, bool) or _blockCount < 0:
        raise _RpcError({"code": -32602, "message": f"Invalid block count: {data.params[0]!r}"})
    # include the newest block in the range (spec: oldestBlock = newest - count)
    _newest = int(_resolveBlockNumber(data.params[1]))
    _oldest = max(_newest - _blockCount, 0)
    return {
        "oldestBlock": hex(_oldest),
        "baseFeePerGas": [],
        "gasUsedRatio": [],
        "reward": [],
    }


def eth_getLogs(data):
    """Filter events emitted by committed transactions.

    Logs are the JSON-encodable event dicts stored in each transaction's
    receipt (see State.execEVMCall → tx.setEvents → makeReceipt).  We match
    them against the same tx-order index that eth_blockNumber / synthetic
    blocks use, so fromBlock/toBlock and each log's blockNumber agree with
    eth_getBlockByNumber.  This is the tx-order convention (NOT the beacon
    height the event captured at emit time), kept consistent on purpose.

    Filters supported: address (list OR-match), topics (positional with None
    wildcards), fromBlock/toBlock (default earliest..latest).
    """
    _requireParams(data, 1)
    _filter = data.params[0]
    if not isinstance(_filter, dict):
        raise _RpcError({"code": -32602, "message": f"Invalid filter: {_filter!r}"})

    # --- address: single addr, or a list matched as OR ----------------------
    _addrFilter = _filter.get("address")
    if _addrFilter is not None:
        if isinstance(_addrFilter, str):
            _addrFilter = [_addrFilter]
        if not isinstance(_addrFilter, list):
            raise _RpcError({"code": -32602, "message": f"Invalid address filter: {_addrFilter!r}"})
        _addrs = []
        for _a in _addrFilter:
            try:
                _addrs.append(w3.to_checksum_address(_a).lower())
            except Exception:
                raise _RpcError({"code": -32602, "message": f"Invalid address filter: {_a!r}"})

    # --- topics: positional, None is a wildcard -----------------------------
    _topicsFilter = _filter.get("topics")
    if _topicsFilter is not None and not isinstance(_topicsFilter, list):
        raise _RpcError({"code": -32602, "message": "topics filter must be a list"})

    # --- block range --------------------------------------------------------
    _from = _resolveBlockNumber(_filter.get("fromBlock", "latest"))
    _to = _resolveBlockNumber(_filter.get("toBlock", "latest"))
    if _from > _to:
        return []
    _count = node.store.txCount()
    _start = max(_from, 0)
    _end = min(_to + 1, _count)

    _results = []
    for _txIndex in range(_start, _end):
        _txs = node.store.getTxsByRange(_txIndex, _txIndex + 1)
        if not _txs or _txs[0] is None:
            continue
        _txid = node.store.getTxHashes()[_txIndex]
        _receipt = node.state.receipts.get(_txid)
        if not _receipt:
            continue
        for _log in _receipt.get("logs", []):
            # address OR-match (case-insensitive)
            if _addrFilter is not None and _log.get("address", "").lower() not in _addrs:
                continue
            if _topicsFilter is not None:
                _logTopics = _log.get("topics", [])
                _matched = True
                for _i, _t in enumerate(_topicsFilter):
                    if _t is None:
                        continue  # wildcard
                    if _i >= len(_logTopics) or _logTopics[_i] != _t:
                        _matched = False
                        break
                if not _matched:
                    continue
            # normalize blockNumber/blockHash to the tx-order convention so
            # clients can correlate the log to the synthetic block
            _log = dict(_log)
            _log["blockNumber"] = hex(_txIndex)
            _log["blockHash"] = _txid
            _results.append(_log)
    return _results


def web3_sha3(data):
    _requireParams(data, 1)
    _payload = data.params[0]
    try:
        _payload = _payload[2:] if _payload.startswith("0x") else _payload
        _payload = bytes.fromhex(_payload)
    except (TypeError, ValueError):
        raise _RpcError({"code": -32602, "message": f"Invalid data: {data.params[0]!r}"})
    return "0x" + w3.keccak(_payload).hex()


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
    "eth_syncing": eth_syncing,
    "eth_accounts": eth_accounts,
    "web3_clientVersion": web3_clientVersion,
    "eth_getBlockTransactionCountByNumber": eth_getBlockTransactionCountByNumber,
    "eth_getBlockTransactionCountByHash": eth_getBlockTransactionCountByHash,
    "eth_getTransactionByBlockNumberAndIndex": eth_getTransactionByBlockNumberAndIndex,
    "eth_getUncleCountByBlockHash": eth_getUncleCountByBlockHash,
    "eth_getUncleCountByBlockNumber": eth_getUncleCountByBlockNumber,
    "eth_feeHistory": eth_feeHistory,
    "eth_getLogs": eth_getLogs,
    "web3_sha3": web3_sha3,
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
