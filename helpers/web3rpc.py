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
from rlp.exceptions import RLPException
from web3.auto import w3

from helpers.datatypes import Transaction
# Re-exported for compatibility: callers (and tests) reach for these through
# web3rpc, and the filter registry must be the SAME object the handlers use.
from .filters import (FILTER_KIND_BLOCK, FILTER_KIND_LOG, FILTER_KIND_PENDING,
                      _filterWindow, _filters, _filtersLock, _newFilter,
                      _requireFilter, _sweepFilters)
from .jsonrpc import (ERR_METHOD_NOT_FOUND, Web3Body, _bodyFromItem,
                      _isNotification, _RpcError)
from .rpcparams import (_looksLikeHash, _parseIndex, _rejectUnsupportedRawTx,
                        _requireAddress, _requireCallObject, _requireHash,
                        _requireParams)
from .utils import hexData, printError

# set by registerNode() before the server starts serving requests
node = None


def registerNode(_node):
    """Inject the running Node instance (called once from RaptorChain.py)."""
    global node
    node = _node


# Block tags that mean "the current tip".  Defined here (not next to the
# filter handlers) because _resolveBlockNumber, which sits at the top of the
# file, is the first user.
_LATEST_TAGS = ("latest", "pending", "safe", "finalized")


# --- method handlers -------------------------------------------------------
# each handler receives (data: Web3Body) and returns the JSON-RPC "result"

def _txIndexForHash(_hash):
    """Resolve a tx/block hash to its index in the global tx order.

    Thin wrapper over Node.txIndexForHash: the txsOrder / type-2 alias
    knowledge belongs to the node, not to the RPC layer.
    """
    return node.txIndexForHash(_hash)


def _restampLog(_log, _blockNumber, _blockHash):
    """Return a copy of a log stamped with the synthetic-block convention.

    Logs are stored exactly as Event.JSONEncodable() emitted them, which means
    a BEACON-height blockNumber (a plain int, not a hex quantity) and a BEACON
    proof blockHash.  Restamping is what lets a client correlate a log with the
    blocks this endpoint serves.

    Shared by _collectLogs and _normalizeReceipt so a receipt's nested logs and
    the eth_getLogs result for the same block cannot disagree.
    """
    _log = dict(_log)
    _log["blockNumber"] = hex(_blockNumber)
    _log["blockHash"] = _blockHash
    return _log


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
        if _blockParam in _LATEST_TAGS:
            return max(node.txCount() - 1, 0)
        elif _blockParam == "earliest":
            return 0
        # a hex height is just a quantity; _parseIndex owns that parsing (and
        # the -32602 on malformed input).  _reprString=False keeps the message
        # as the bare value, which is what this method has always reported.
        return _parseIndex(_blockParam, "block param", _reprString=False)
    # numeric block height passed directly (reject bool/None/dict/float)
    if isinstance(_blockParam, int) and not isinstance(_blockParam, bool):
        return _blockParam
    raise _RpcError({"code": -32602, "message": f"Invalid block param: {_blockParam!r}"})


def eth_getBalance(data):
    _requireParams(data, 1)
    _acct = node.state.getAccount(_requireAddress(data.params[0]), True)
    # A negative balance is rendered as a negative quantity (e.g. "-0x5") rather
    # than clamped to zero.  Balances are not supposed to go negative, so this is
    # an intentional canary: a client may choke on the malformed quantity, but
    # clamping would hide the real state defect upstream.  See docs/rpc.md
    # (POST /web3) before "fixing" this.
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
    return hex(max(node.txCount() - 1, 0))


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
    _env = node.state.eth_Call(_requireCallObject(data))
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
    _rawTx = data.params[0]
    # Reject unsupported types (EIP-1559/2930/...) and non-hex input up front,
    # as a client-side -32602 rather than a decode blow-up later.
    _rejectUnsupportedRawTx(_rawTx)
    try:
        _txid = node.integrateETHTransaction(_rawTx)
    except RLPException as e:
        # A payload that is valid hex but not a decodable legacy tx (wrong field
        # count, trailing bytes, truncated list, ...) is still the client's
        # mistake, not an internal node fault — report it as invalid params.
        # RLPException is the base of both DecodingError and
        # ObjectDeserializationError, and during ingest the only RLP work is
        # decoding client-supplied bytes, so this cannot mask a node-side bug.
        raise _RpcError({"code": -32602, "message": f"Invalid raw transaction: {e}"})
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
    # the slot is a JSON-RPC quantity; _parseIndex owns that parsing.
    # _reprString=False keeps the bare-value message this method has always
    # reported ("Invalid storage slot: nope", not "'nope'").
    _slot = _parseIndex(data.params[1], "storage slot", _reprString=False)
    # Ethereum returns 0x0 for unset storage slots, not an error.
    return hex(int(node.state.getAccount(_requireAddress(data.params[0]), True).storage.get(int(_slot), 0)))


def eth_getTransactionByHash(data):
    _requireParams(data, 1)
    # the node method indexes the store with this value, so a non-string
    # (e.g. 123) raised "'NoneType' object is not subscriptable" -> -32603
    return node.ethGetTransactionByHash(_requireHash(data.params[0]))


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
        _hashes = node.txHashes()
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
    _tx = node.txAtBlockNumber(_blockNumber)
    if _tx is None:
        return None
    result = _syntheticTxBlock(_tx, _blockNumber)
    if not _blockTx:  # hashes only
        result["transactions"] = [result["transactions"][0]["hash"]]
    return result


def eth_getBlockByHash(data):
    _requireParams(data, 1)
    # a non-string argument (e.g. a list) used to reach the blocksByHash dict
    # lookup and raise "unhashable type" -> -32603 internal error
    _hash = _requireHash(data.params[0])
    _fullTx = data.params[1] if len(data.params) > 1 else False
    # beacon proofs still resolve to real beacon blocks
    _block = node.state.beaconChain.blocksByHash.get(_hash)
    if _block is not None:
        result = _block.web3Returnable()
        if _fullTx:  # fetch transactions as well
            # A beacon block can name a transaction this node's store does not
            # hold (e.g. a peer never relayed it).  Those come back as None from
            # the getter now, and a malformed stored tx can still raise, so both
            # are skipped rather than failing the WHOLE block with -32603 and
            # making it unreadable.  Deliberate trade-off: the full-transaction
            # list can then be shorter than the hash list /
            # eth_getBlockTransactionCountByHash, which is preferable to
            # refusing to serve the block at all.
            _resolved = []
            for _txid in result["transactions"]:
                try:
                    _tx = node.ethGetTransactionByHash(_txid)
                except Exception:
                    continue
                if _tx is not None:
                    _resolved.append(_tx)
            result["transactions"] = _resolved
        return result
    # otherwise treat the hash as a transaction hash -> synthetic block
    _tx = node.getTransaction(_hash)
    if not _tx:
        return None
    # Look up the tx's position in the ordered list.  txsOrder stores the
    # type-0 (raptor) hash; node.getTransaction already resolved any type-2
    # (eth) alias above, so we just need the type-0 hash to index into
    # txsOrder.  Node.txIndexForHash owns that resolution.
    _index = node.txIndexForHash(_hash)
    if _index is None:
        return None
    _hashes = node.txHashes()
    result = _syntheticTxBlock(_tx, _index,
                               parentHash=(_hashes[_index - 1] if _index > 0 else None))
    if not _fullTx:  # hashes only
        result["transactions"] = [result["transactions"][0]["hash"]]
    return result


def _blockParamToTxIndex(_param):
    """Resolve a block parameter to a tx-order index, or None if unknown.

    Ints, hex heights and tags ("latest", ...) go through the shared
    resolver.  A 32-byte hash is treated as a synthetic block hash — and a
    synthetic block's hash IS its transaction hash — so it resolves through
    _txIndexForHash.  A beacon-block hash resolves to None: beacon blocks
    have no tx-order number, matching eth_getBlockByNumber, which cannot
    address them either.
    """
    if _looksLikeHash(_param):
        return _txIndexForHash(_param)
    return int(_resolveBlockNumber(_param))


def _normalizeReceipt(_txid, _blockNumber, _blockHash, _txIndexInBlock):
    """Return a copy of a stored receipt restamped with synthetic-block metadata.

    Stored receipts carry blockHash = tx.epoch (a beacon-chain hash) and a
    hardcoded transactionIndex of '0x1', neither of which lines up with the
    synthetic blocks served by eth_getBlockByNumber, where a block holds
    exactly one transaction at index 0 and the block hash is the tx hash.
    Restamping here makes getBlockReceipts(n) correlate with
    getBlockByNumber(n) without altering any existing method's output.

    Returns None when no receipt is available (a transaction that was stored
    but never executed, or whose receipt was lost).
    """
    _receipt = node.txReceipt(_txid)
    if not _receipt:
        return None
    _receipt = dict(_receipt)
    _receipt["blockNumber"] = hex(_blockNumber)
    _receipt["blockHash"] = _blockHash
    _receipt["transactionIndex"] = hex(_txIndexInBlock)
    # The nested logs carry emit-time beacon metadata, so without this a
    # receipt would report blockNumber "0x1" while its own logs reported the
    # beacon height, and getLogs for the same block would disagree with both.
    # Absence of a logs key is preserved rather than filled in.
    if isinstance(_receipt.get("logs"), list):
        _receipt["logs"] = [_restampLog(_log, _blockNumber, _blockHash)
                            for _log in _receipt["logs"]]
    return _receipt


def eth_getBlockReceipts(data):
    """Return the receipts of the synthetic block at the given number or hash.

    Uses the same convention as eth_getBlockByNumber: blocks are keyed on the
    global transaction order and hold exactly one transaction, so an existing
    block yields a single-element list.  An existing block whose transaction
    has no stored receipt yields []; an unknown or out-of-range block yields
    null.

    Beacon-block hashes yield null — they are not part of the tx-order
    numbering, exactly as with eth_getBlockByNumber.
    """
    _requireParams(data, 1)
    _index = _blockParamToTxIndex(data.params[0])
    if _index is None or _index < 0 or _index >= node.txCount():
        return None
    _txid = node.txHashes()[_index]
    _receipt = _normalizeReceipt(_txid, _index, _txid, 0)
    return [_receipt] if _receipt is not None else []


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


def net_listening(data):
    """The endpoint is always serving; nothing gates readiness here."""
    return True


def net_peerCount(data):
    """Number of peers currently registered, as a hex quantity.

    getattr guards the window before the node has loaded its peer list.
    """
    return hex(len(getattr(node, "peers", None) or []))


def eth_maxPriorityFeePerGas(data):
    """Always "0x0": there is no priority-fee market on this chain.

    eth_gasPrice is the entire price of a transaction here, so a priority fee
    of zero is the truthful answer, not a placeholder.  Answering instead of
    returning method-not-found lets EIP-1559-aware clients (viem/ethers
    estimateFeesPerGas) finish fee estimation against a pre-1559 chain.
    """
    return "0x0"


def eth_getBlockTransactionCountByNumber(data):
    _requireParams(data, 1)
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    if node.txAtBlockNumber(_blockNumber) is None:
        return None
    # a synthetic block holds exactly one transaction, so the count is always
    # 0x1 — no need to build the block (and its web3Returnable tx) to learn it
    return "0x1"


def eth_getBlockTransactionCountByHash(data):
    _requireParams(data, 1)
    # non-string arguments were unhashable -> TypeError -> -32603
    _hash = _requireHash(data.params[0])
    # beacon proofs still resolve to real beacon blocks
    _block = node.state.beaconChain.blocksByHash.get(_hash)
    if _block is not None:
        return hex(len(_block.web3Returnable()["transactions"]))
    _index = _txIndexForHash(_hash)
    if _index is None:
        return None
    if node.txAtBlockNumber(_index) is None:
        return None
    # single-transaction synthetic block: the count is always 0x1
    return "0x1"


def eth_getTransactionByBlockNumberAndIndex(data):
    """Return the transaction at the given index of a synthetic block.

    Synthetic blocks always contain exactly one transaction, so index 0
    returns that transaction and any other index returns null.  Beacon-block
    hashes are not part of the tx-index numbering and return null.
    """
    _requireParams(data, 2)
    _index = _parseIndex(data.params[1], "transaction index")
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    if _index != 0:
        return None
    _tx = node.txAtBlockNumber(_blockNumber)
    if _tx is None:
        return None
    # the block's single transaction IS the requested one; build it directly
    # rather than assembling a whole block dict to index back into it
    return Transaction(_tx).web3Returnable()


def eth_getTransactionByBlockHashAndIndex(data):
    """Return the transaction at the given index of a synthetic block, by hash.

    Mirrors eth_getTransactionByBlockNumberAndIndex: synthetic blocks are
    single-transaction, so index 0 resolves and any other index returns null.
    Beacon-block hashes are not part of the tx-index numbering and return
    null, as does an unknown hash.
    """
    _requireParams(data, 2)
    _indexInBlock = _parseIndex(data.params[1], "transaction index")
    if _indexInBlock != 0:
        return None
    # validation is required BEFORE _txIndexForHash: a non-string argument is
    # unhashable, so blocksByHash.get() raised TypeError -> -32603.  Every other
    # hash-taking method is guarded the same way; this one was missed.
    _blockIndex = _txIndexForHash(_requireHash(data.params[0]))
    if _blockIndex is None:
        return None
    _tx = node.txAtBlockNumber(_blockIndex)
    if _tx is None:
        return None
    # the block's single transaction IS the requested one
    return Transaction(_tx).web3Returnable()


def eth_getUncleCountByBlockHash(data):
    _requireParams(data, 1)
    # non-string arguments were unhashable -> TypeError -> -32603
    _hash = _requireHash(data.params[0])
    if node.state.beaconChain.blocksByHash.get(_hash) is None \
            and _txIndexForHash(_hash) is None:
        return None
    return "0x0"


def eth_getUncleCountByBlockNumber(data):
    _requireParams(data, 1)
    _blockNumber = int(_resolveBlockNumber(data.params[0]))
    # Deliberately an INDEX-RANGE check, not a payload lookup: this method
    # answers "does the block exist", and a block exists as soon as it has an
    # order slot.  Using txAtBlockNumber() here would additionally require the
    # stored payload to be readable, so a degraded store would turn a valid
    # "0x0" into null — a behaviour change with no upside, since the uncle
    # count never needs the transaction itself.
    if _blockNumber < 0 or _blockNumber >= node.txCount():
        return None
    return "0x0"


def eth_getUncleByBlockHashAndIndex(data):
    """Always null: this chain has no uncles.

    eth_getUncleCountByBlockHash already answers 0x0, so there is no uncle to
    return.  Fabricating an object would be strictly worse than the honest
    null — a client would trust it.
    """
    _requireParams(data, 2)
    _parseIndex(data.params[1], "uncle index")
    return None


def eth_getUncleByBlockNumberAndIndex(data):
    """Always null: this chain has no uncles (see the by-hash variant)."""
    _requireParams(data, 2)
    _parseIndex(data.params[1], "uncle index")
    return None


# NOTE: eth_feeHistory is deliberately NOT implemented.  RaptorChain has no
# EIP-1559 fee market (no base fee / priority fee — only a flat eth_gasPrice),
# so any baseFeePerGas/gasUsedRatio/reward response would be fabricated data.
# Returning method-not-found makes ethers/viem/MetaMask fall back to the real
# eth_gasPrice, which is the correct behavior for a pre-1559 chain.  ethers in
# particular never even calls eth_feeHistory here because our blocks do not
# expose baseFeePerGas.
#
# eth_getProof is also deliberately absent.  A real account/storage proof needs
# a Merkle-Patricia trie over committed state, and this node's state root is not
# bound to account balances, so any "proof" produced here would be meaningless.
# A light client or bridge that trusted it would be actively misled, which is
# worse than the honest method-not-found.
#
# eth_subscribe is absent for a transport reason, not a policy one: it is a
# WebSocket-only API and /web3 is HTTP POST.


def _normalizeLogFilter(_filter):
    """Validate and normalize a log filter's address/topics constraints.

    Returns (addrs, topics): addrs is a list of lowercased checksummed
    addresses, or None for "no address restriction"; topics is the positional
    list (None entries are wildcards), or None.

    Shared by eth_getLogs and the log filters so the two can never disagree
    about what a filter means.

    KNOWN LIMITATION (inherited unchanged from the original eth_getLogs): a
    topic position is compared for plain equality, so Ethereum's OR-form
    ({"topics": [[A, B]]}) is accepted but never matches.  Fixing it means
    changing matching semantics for eth_getLogs too, so it is left as-is
    here and pinned by a test rather than changed in passing.
    """
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
    else:
        _addrs = None

    # --- topics: positional, None is a wildcard -----------------------------
    _topicsFilter = _filter.get("topics")
    if _topicsFilter is not None and not isinstance(_topicsFilter, list):
        raise _RpcError({"code": -32602, "message": "topics filter must be a list"})

    return _addrs, _topicsFilter


def _collectLogs(_start, _end, _addrs, _topicsFilter):
    """Collect matching logs for the tx-order indices in [_start, _end).

    Each returned log is restamped with the synthetic-block convention
    (blockNumber = tx-order index, blockHash = tx hash) so clients can
    correlate it with eth_getBlockByNumber.  Shared by eth_getLogs and by
    eth_getFilterChanges/eth_getFilterLogs.
    """
    if _start >= _end:
        return []
    # hoisted out of the loop: getTxHashes() copies the entire order list, so
    # calling it per iteration made the scan O(n) in copies as well as in work
    _hashes = node.txHashes()
    # One store read for the whole window.  The scan only needs to know whether
    # each block's payload EXISTS (the logs come from state.receipts), so
    # fetching the range in a single call avoids a lock + Python frame per
    # block — measured at ~0.36us/block when done per-iteration.
    _txs = node.txsInRange(_start, min(_end, len(_hashes)))
    _results = []
    for _offset, _tx in enumerate(_txs):
        if _tx is None:
            continue
        _txIndex = _start + _offset
        _txid = _hashes[_txIndex]
        _receipt = node.state.receipts.get(_txid)
        if not _receipt:
            continue
        for _log in _receipt.get("logs", []):
            # address OR-match (case-insensitive)
            if _addrs is not None and _log.get("address", "").lower() not in _addrs:
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
            _results.append(_restampLog(_log, _txIndex, _txid))
    return _results


def eth_getLogs(data):
    """Filter events emitted by committed transactions.

    Logs are the JSON-encodable event dicts stored in each transaction's
    receipt (see State.execEVMCall → tx.setEvents → makeReceipt).  We match
    them against the same tx-order index that eth_blockNumber / synthetic
    blocks use, so fromBlock/toBlock and each log's blockNumber agree with
    eth_getBlockByNumber.  This is the tx-order convention (NOT the beacon
    height the event captured at emit time), kept consistent on purpose.

    Filters supported: address (list OR-match), topics (positional with None
    wildcards), fromBlock/toBlock (default latest..latest).  Matching is
    delegated to _normalizeLogFilter/_collectLogs, which the polling log
    filters share.
    """
    _requireParams(data, 1)
    _filter = data.params[0]
    if not isinstance(_filter, dict):
        raise _RpcError({"code": -32602, "message": f"Invalid filter: {_filter!r}"})
    _addrs, _topicsFilter = _normalizeLogFilter(_filter)

    # --- block range --------------------------------------------------------
    _from = _resolveBlockNumber(_filter.get("fromBlock", "latest"))
    _to = _resolveBlockNumber(_filter.get("toBlock", "latest"))
    if _from > _to:
        return []
    return _collectLogs(max(_from, 0), min(_to + 1, node.txCount()), _addrs, _topicsFilter)


def web3_sha3(data):
    _requireParams(data, 1)
    _payload = data.params[0]
    try:
        _payload = _payload[2:] if _payload.startswith("0x") else _payload
        _payload = bytes.fromhex(_payload)
    except (AttributeError, TypeError, ValueError):
        # AttributeError covers a non-string argument (a number, null, a list),
        # which used to escape as an unhandled -32603 internal error.
        raise _RpcError({"code": -32602, "message": f"Invalid data: {data.params[0]!r}"})
    # keccak() returns HexBytes, whose .hex() ALREADY carries the "0x" prefix,
    # so the previous "0x" + ....hex() returned a double-prefixed hash
    # ("0x0xd4fd...", 68 characters) that every client-side hex parser rejects —
    # an odd/even-length disaster this codebase has hit before (see hexData).
    return hexData(w3.keccak(_payload))


# --- polling filters ---------------------------------------------------------
# The registry itself lives in helpers/filters.py; the handlers below are the
# thin JSON-RPC surface over it.  Cursors are TX-ORDER indices, like every
# other block-number answer on this endpoint: a synthetic block holds exactly
# one transaction, and its hash IS that transaction's hash.

def eth_newBlockFilter(data):
    """Register a filter reporting newly stored transactions.

    A synthetic block's hash is its transaction hash, so the reported ids are
    exactly what eth_getBlockByHash accepts.  The cursor starts at the current
    tip, so only blocks stored from now on are reported.
    """
    with _filtersLock:
        return _newFilter(FILTER_KIND_BLOCK, node.txCount())


def eth_newPendingTransactionFilter(data):
    """Register a filter that never reports anything.

    This chain has no separate pending set: a transaction is written to the
    store as soon as it is accepted, so there is no observable difference
    between "pending" and "stored".  Rather than alias eth_newBlockFilter and
    claim a mempool view that does not exist, this stays honestly empty.
    """
    with _filtersLock:
        return _newFilter(FILTER_KIND_PENDING, 0, _endIndex=0)


def eth_newFilter(data):
    """Register a log filter.

    fromBlock defaults to "latest", which for a *filter* means "start at the
    current tip" — a subscription reports only new logs, whereas an explicit
    fromBlock replays from that index on the first poll.  toBlock "latest"
    keeps tracking new blocks; an explicit toBlock bounds the filter.
    """
    _requireParams(data, 1)
    _filter = data.params[0]
    if not isinstance(_filter, dict):
        raise _RpcError({"code": -32602, "message": f"Invalid filter: {_filter!r}"})
    _addrs, _topicsFilter = _normalizeLogFilter(_filter)

    _fromParam = _filter.get("fromBlock", "latest")
    _toParam = _filter.get("toBlock", "latest")
    if isinstance(_fromParam, str) and _fromParam in _LATEST_TAGS:
        _cursor = node.txCount()
    else:
        _cursor = max(_resolveBlockNumber(_fromParam), 0)
    if isinstance(_toParam, str) and _toParam in _LATEST_TAGS:
        _endIndex = None
    else:
        _endIndex = _resolveBlockNumber(_toParam) + 1

    with _filtersLock:
        return _newFilter(FILTER_KIND_LOG, _cursor, _endIndex=_endIndex,
                          _startIndex=_cursor, _addrs=_addrs,
                          _topicsFilter=_topicsFilter)


def eth_getFilterChanges(data):
    """Return everything the filter has seen since the previous poll.

    The cursor advances past whatever is returned, so consecutive polls never
    repeat a block or log.  An unchanged chain yields [], never null.
    """
    _requireParams(data, 1)
    with _filtersLock:
        _filter = _requireFilter(data.params[0])
        _filter["lastPolledAt"] = time.monotonic()
        if _filter["kind"] == FILTER_KIND_PENDING:
            return []
        _start, _end = _filterWindow(_filter, node.txCount())
        if _filter["kind"] == FILTER_KIND_BLOCK:
            _changes = node.txHashes()[_start:_end]
        else:
            _changes = _collectLogs(_start, _end, _filter["addrs"], _filter["topics"])
        # max() keeps the cursor monotonic.  It matters for a filter created
        # with a fromBlock beyond the current tip: _filterWindow collapses such
        # a window to the tip, and assigning that unconditionally would make the
        # filter start reporting from now instead of waiting for fromBlock.
        _filter["cursor"] = max(_filter["cursor"], _end)
        return _changes


def eth_getFilterLogs(data):
    """Return every log a log filter matches over its whole range.

    Unlike eth_getFilterChanges this does NOT advance the cursor (per spec),
    so repeated calls return the same result.  Block and pending filters have
    no log stream and yield an empty list.
    """
    _requireParams(data, 1)
    with _filtersLock:
        _filter = _requireFilter(data.params[0])
        _filter["lastPolledAt"] = time.monotonic()
        if _filter["kind"] != FILTER_KIND_LOG:
            return []
        _blockEnd = _filterWindow(_filter, node.txCount())[1]
        _first = _filter["startIndex"] if _filter["startIndex"] is not None else 0
        return _collectLogs(_first, _blockEnd, _filter["addrs"], _filter["topics"])


def eth_uninstallFilter(data):
    """Remove a filter.  Unknown or expired ids return False (not an error)."""
    _requireParams(data, 1)
    _filterId = data.params[0]
    if not isinstance(_filterId, str):
        raise _RpcError({"code": -32602, "message": f"Invalid filter id: {_filterId!r}"})
    with _filtersLock:
        _sweepFilters()
        return _filters.pop(_filterId, None) is not None


# JSON-RPC 2.0 error codes and the request/response envelope live in
# helpers/jsonrpc.py and are re-exported above so existing importers keep
# working.  No __all__ here: it would restrict `from helpers.web3rpc import *`
# to the three names below and silently hide the 41 eth_* handlers.


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
    "eth_getBlockReceipts": eth_getBlockReceipts,
    "eth_chainId": lambda data: hex(node.state.chainID),
    "eth_syncing": eth_syncing,
    "eth_accounts": eth_accounts,
    "web3_clientVersion": web3_clientVersion,
    "net_listening": net_listening,
    "net_peerCount": net_peerCount,
    "eth_maxPriorityFeePerGas": eth_maxPriorityFeePerGas,
    "eth_getBlockTransactionCountByNumber": eth_getBlockTransactionCountByNumber,
    "eth_getBlockTransactionCountByHash": eth_getBlockTransactionCountByHash,
    "eth_getTransactionByBlockNumberAndIndex": eth_getTransactionByBlockNumberAndIndex,
    "eth_getTransactionByBlockHashAndIndex": eth_getTransactionByBlockHashAndIndex,
    "eth_getUncleCountByBlockHash": eth_getUncleCountByBlockHash,
    "eth_getUncleCountByBlockNumber": eth_getUncleCountByBlockNumber,
    "eth_getUncleByBlockHashAndIndex": eth_getUncleByBlockHashAndIndex,
    "eth_getUncleByBlockNumberAndIndex": eth_getUncleByBlockNumberAndIndex,
    "eth_getLogs": eth_getLogs,
    "web3_sha3": web3_sha3,
    "eth_newFilter": eth_newFilter,
    "eth_newBlockFilter": eth_newBlockFilter,
    "eth_newPendingTransactionFilter": eth_newPendingTransactionFilter,
    "eth_getFilterChanges": eth_getFilterChanges,
    "eth_getFilterLogs": eth_getFilterLogs,
    "eth_uninstallFilter": eth_uninstallFilter,
}


# --- HTTP entry point ------------------------------------------------------
# These are module-level rather than nested inside createRouter: none of them
# capture anything from an enclosing scope (they only touch module globals), so
# nesting them bought nothing and made the dispatch path harder to follow.

def _handleSingle(data: Web3Body):
    """Process one JSON-RPC request.

    Returns the response dict, or None when the request is a notification
    (no id) so the caller can omit it from the HTTP response per spec.
    """
    _begin = time.time()

    if node is None:
        _respdict = {"id": data.id, "jsonrpc": "2.0",
                     "error": {"code": -32000, "message": "Node not ready"}}
        return None if _isNotification(data) else _respdict

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
    # JSON-RPC 2.0: only a request that OMITS the id member is a
    # notification.  An explicit "id": null is an ordinary request and MUST
    # be answered — see _isNotification.
    return None if _isNotification(data) else _respdict


def _jsonResponse(_payload):
    """Serialize a JSON-RPC response body."""
    return fastapi.Response(content=json.dumps(_payload),
                            media_type='application/json')


def _dispatchOne(_item):
    """Validate one raw request item, then handle it.

    Returns the response dict, or None when nothing should be sent back
    (a notification).
    """
    _body, _error = _bodyFromItem(_item)
    if _error is not None:
        return _error
    return _handleSingle(_body)


def createRouter(app: fastapi.FastAPI):
    """Attach the POST /web3 route to the given FastAPI app."""

    @app.post("/web3")
    def handleWeb3Request(data: Any = fastapi.Body(default=None)):
        # The body arrives as raw JSON and each item is validated individually
        # (see _bodyFromItem): letting pydantic validate a
        # Union[Web3Body, List[Web3Body]] body meant ONE malformed member made
        # the whole batch fail with HTTP 422, discarding every valid sibling
        # request, and answered with a body a JSON-RPC client cannot read.
        if isinstance(data, list):
            # Batch request: a JSON array of requests -> array of responses.
            # Notifications (no id) are processed but omitted from the response.
            _responses = []
            for _item in data:
                _r = _dispatchOne(_item)
                if _r is not None:
                    _responses.append(_r)
            return _jsonResponse(_responses)
        # Single request
        _respdict = _dispatchOne(data)
        if _respdict is None:
            # notification — no content
            return fastapi.Response(status_code=204)
        return _jsonResponse(_respdict)

    return handleWeb3Request
