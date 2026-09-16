"""Shared utility helpers for RaptorChain.

Formatting, error reporting, interactive prompts and the transaction/block
signing idioms shared by the node and the standalone producers.

These functions were previously duplicated (formatAddress appeared three
times in RaptorChain.py alone) or lived as module-level functions mixed
into the main file.

The packed-hashing helpers live in helpers/keccaktools.py; packedKeccak is
re-exported here because signTxData() and beaconBlockHash() below are defined
in terms of it.
"""

import sys
import time
from functools import lru_cache

import rich

import eth_abi
from web3.auto import w3
from eth_account.messages import encode_defunct

from . import constants
from .keccaktools import packedKeccak


def _formatAddress(_addr):
    """Uncached core: normalize a 20-byte integer or hex string to EIP-55.

    Accepts either a 20-byte integer or a hex string.  This replaces the
    three identical copies that previously lived in Transaction,
    State.CallBlankTransaction and State.

    Kept separate from the cached path so the memoized wrapper has exactly one
    thing to remember, and so this stays the verbatim original behaviour --
    same results and same exceptions for the same input.
    """
    if type(_addr) == int:
        return w3.to_checksum_address(_addr.to_bytes(20, "big"))
    return w3.to_checksum_address(_addr)


# formatAddress sits on the per-opcode path (State.getAccount formats its
# argument, and getAccount is reached from essentially every opcode and every
# RPC read), while w3.to_checksum_address re-derives the whole EIP-55 digest on
# EVERY call -- measured ~24-29us even when the input is already checksummed.
# The same few addresses are formatted over and over, so results are memoized.
#
# A bounded cache is not optional: the key is whatever the caller passes, and
# on a public RPC that includes arbitrary attacker-chosen strings, so an
# unbounded cache is a way to grow memory without limit.  Size matches
# keccaktools._isChecksumAddress.
_FORMAT_ADDRESS_CACHE_SIZE = 1 << 16


@lru_cache(maxsize=_FORMAT_ADDRESS_CACHE_SIZE)
def _cachedFormatAddress(_addrType, _addr):
    """Memoize _formatAddress, INCLUDING the way it fails.

    Failures are returned as the exception OBJECT rather than raised, because
    lru_cache only memoizes successful returns: a raised exception escapes the
    wrapper and is never cached, so a malformed address would be re-validated
    (and re-raised) on every single call.  Handing the exception back turns the
    second and later calls for a bad input into a cache hit as well.

    Callers must go through formatAddress(), which re-raises it.

    _addrType is part of the cache KEY, not decoration.  _formatAddress branches
    on type() (an int address is rendered from its bytes, anything else is passed
    to web3), so behaviour is a function of the type AND the value -- while
    lru_cache keys on the value alone.  For a single argument, functools
    fast-paths one whose type is EXACTLY int or str (it uses the raw value as the
    dict key) and wraps every other type in a _HashedSeq, whose __eq__ is
    list.__eq__ and so compares element-wise.  Two consequences, both measured:

        formatAddress(0)   vs formatAddress(False)  -> insulated
            a raw int key never equals a _HashedSeq, although 0 == False
        formatAddress(0.0) vs formatAddress(False)  -> SHARED SLOT
            both are _HashedSeq: 0.0 == False, and their hashes match

    An untyped key therefore served the WRONG outcome for whichever of a
    colliding pair was cached second: formatAddress(0.0) raised the ValueError
    that belongs to False, and formatAddress(memoryview(b"..")) returned the
    success cached for the equal bytes value.  In the reverse order it is worse
    than cosmetic -- a VALID bytes address then took the memoryview's TypeError,
    and kept raising it for the life of the process.  Passing type() as a second
    argument makes the key a 2-tuple, which functools always wraps in a
    _HashedSeq, so the type is compared as well and each type gets its own slot.
    (An exact int or str is insulated either way, but relying on that would mean
    relying on a functools implementation detail for correctness.)

    Unhashable values still fail the lookup and are handled in formatAddress;
    classes are always hashable, so the type argument never causes that.
    """
    try:
        return _formatAddress(_addr)
    except Exception as _error:
        return _error


def formatAddress(_addr):
    """Normalize an address to a checksummed hex string (memoized).

    Same results and the same exceptions as the original implementation; the
    only change is that repeated inputs are served from a cache.
    """
    try:
        # type() first: see _cachedFormatAddress for why the key must be typed
        _result = _cachedFormatAddress(type(_addr), _addr)
    except TypeError:
        # Unhashable argument (bytearray, list, dict, ...) -- the lru_cache
        # lookup itself refuses it before our body can run.  Falling back to the
        # uncached core preserves the ORIGINAL behaviour exactly: to_checksum_address
        # really does accept a 20-byte bytearray, and for the types it rejects it
        # raises its own TypeError, whose message callers may match on.
        # _cachedFormatAddress never raises TypeError itself (it catches
        # Exception), so a TypeError here can only come from the lookup.
        return _formatAddress(_addr)
    if isinstance(_result, Exception):
        raise _result
    return _result


def hexData(_value):
    """Render binary data as 0x-prefixed hex, for JSON-RPC DATA fields.

    bytes.hex() has no "0x" prefix, but every JSON-RPC DATA field must carry
    one, so values held as raw bytes were being served as malformed hex and
    made client-side parsers throw (ethers' getBytes() rejects a hex string
    that does not start with 0x).  Transaction stores r/s as raw byte slices
    for legacy transactions, and the genesis beacon's parent is bytes.

    Hex strings are returned unchanged: callers that already hold one (the
    legacy decoder output for MetaMask transactions) must keep the exact
    representation they had, and strings that are not hex at all (e.g. an
    EIP-1559 v value) must not be re-encoded here.

    HexBytes also subclasses bytes, but its .hex() already includes the "0x"
    prefix, so the prefix is added only when it is missing.  Adding one
    blindly would produce the "0x0x..." hash this codebase has hit before.
    """
    if isinstance(_value, (bytes, bytearray)):
        _hex = _value.hex()
        return _hex if _hex.startswith("0x") else "0x" + _hex
    return _value


def printError(errorMessage):
    """Print an error message, falling back to plain print if rich fails."""
    try:
        rich.print(f"[red]{errorMessage}[/red]")
    except Exception:
        print(errorMessage)


class NonInteractiveError(Exception):
    """Raised when operator input is required but no terminal is attached.

    Carries the question so the caller (or the top-level handler) can report
    exactly which prompt could not be answered instead of an opaque EOFError.
    """
    def __init__(self, question):
        self.question = question
        super().__init__(f"No terminal attached, cannot ask: {question}")

    def __str__(self):
        return (f"Operator input required ({self.question}) but stdin is not "
                f"an interactive terminal")


def isInteractive():
    """Return True when stdin is an attached terminal.

    False for pipes, redirects, /dev/null and closed stdin, so callers can
    never block an unattended (systemd, container, CI) startup.
    """
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, AttributeError):
        # stdin replaced by a non-file object that has no isatty()
        return False


def promptInteractive(question, default=None):
    """Ask the operator a question, keeping the interactive UX unchanged.

    On a terminal this is exactly ``input(question)``: the prompt is shown and
    the typed answer is returned verbatim.

    Without a terminal it never blocks. If ``default`` is provided that value
    is returned (with a notice); otherwise NonInteractiveError is raised so
    the caller fails with a clear message rather than an EOFError deep in a
    constructor.

    ``default`` is compared against None, so falsy defaults such as "" or 0
    are honoured.
    """
    if isInteractive():
        try:
            return input(question)
        except EOFError:
            # terminal went away between the check and the prompt
            pass
    if default is not None:
        printError(f"Non-interactive: {question.strip()} -> using default {default!r}")
        return default
    raise NonInteractiveError(question)


def isNotComment(line):
    """Filter predicate for peers.txt lines.

    Returns True for lines that are neither comments (contain '#') nor the
    DISMISSCONFIG directive.
    """
    return (("#" not in line) and (line != "DISMISSCONFIG"))


def lastOf(lst, default=None):
    """Return the last element of a list, or ``default`` when empty/missing.

    Replaces the ``seq[len(seq)-1]`` anti-pattern that was copy-pasted
    through RaptorBlockSigner, RaptorBlockProducer and Wallet.
    """
    return lst[-1] if lst else default


def signTxData(acct, txdata):
    """Sign a RaptorChain-native transaction payload with the given account.

    Returns the wire-format transaction dict ``{"data", "sig", "hash"}``
    built from ``txdata`` (a JSON string).  This is the exact idiom that
    was duplicated at 7 call sites across RaptorChain.py, blockProducer.py
    and raptormasternode.py.
    """
    sig = acct.sign_message(encode_defunct(text=txdata)).signature.hex()
    return {"data": txdata, "sig": sig,
            "hash": packedKeccak(["string"], [txdata]).hex()}


def beaconBlockHash(parent, timestamp, messages, parentTxRoot, miner):
    """Compute the beacon block proof (the miningData.proof value).

    bRoot = keccak(parent (bytes32), timestamp (uint256),
                   keccak(messages) (bytes32), parentTxRoot (bytes32),
                   miner (address))
    proof = keccak(bRoot (bytes32), nonce=0 (uint256))

    ``parentTxRoot`` may be a HexBytes, a 0x-prefixed hex string, or a bare
    hex string (as produced by ``txsRoot().hex()``) — it is normalized to
    the 0x-prefixed form web3 expects for bytes32.  This mirrors the
    original inline code, which passed ``parentTxRoot.hex()`` directly.

    One definition shared by the in-process producer (RaptorChain.py), the
    REST client producers (blockProducer.py, raptormasternode.py) and the
    datatypes module (helpers/datatypes.py).  Note that blockProducer.py's
    old copy was missing the parentTxRoot term (pre-STI-upgrade formula);
    it is fixed by this shared implementation.
    """
    messagesHash = w3.keccak(bytes.fromhex(messages)).hex()
    _txRoot = parentTxRoot.hex() if hasattr(parentTxRoot, "hex") else str(parentTxRoot)
    if not _txRoot.startswith("0x"):
        _txRoot = "0x" + _txRoot
    bRoot = packedKeccak(
        ["bytes32", "uint256", "bytes32", "bytes32", "address"],
        [parent, int(timestamp), messagesHash, _txRoot, miner]).hex()
    return packedKeccak(["bytes32", "uint256"], [bRoot, int(0)]).hex()


def assembleBlockData(miner, height, parent, parentTxRoot, messagesHex, timestamp=None):
    """Build the blockData dict shared by all three block producers.

    Returns the dict with miningData.proof already populated via
    beaconBlockHash(); the caller then signs it (usually through
    signBlockData()).  ``parentTxRoot`` may be a HexBytes, a 0x-prefixed
    hex string, or a bare hex string; it is stored (and hashed) in the
    0x-prefixed form so the submitted blockData matches the historical
    wire format (which any node compares against ``txsRoot().hex()``).
    """
    _txRoot = parentTxRoot.hex() if hasattr(parentTxRoot, "hex") else str(parentTxRoot)
    if not _txRoot.startswith("0x"):
        _txRoot = "0x" + _txRoot
    blockData = {"parentTxRoot": _txRoot,
                 "miningData": {"miner": miner, "nonce": 0, "difficulty": 1,
                                "miningTarget": constants.MAX_TARGET,
                                "proof": None},
                 "height": height, "parent": parent,
                 "messages": messagesHex,
                 "timestamp": (int(time.time()) if timestamp is None else int(timestamp)),
                 "son": constants.ZERO_HASH,
                 "signature": {"v": None, "r": None, "s": None, "sig": None}}
    blockData["miningData"]["proof"] = beaconBlockHash(
        blockData["parent"], blockData["timestamp"], blockData["messages"],
        blockData["parentTxRoot"], blockData["miningData"]["miner"])
    return blockData


def signBlockData(acct, blockData):
    """Sign a blockData dict's proof and fill its signature fields.

    Mutates and returns ``blockData`` with ``signature.v/r/s/sig`` set
    (same behavior as the tail of the three duplicated buildBlock()).
    """
    _sig = acct.signHash(blockData["miningData"]["proof"])
    blockData["signature"]["v"] = _sig.v
    blockData["signature"]["r"] = _sig.r
    blockData["signature"]["s"] = _sig.s
    blockData["signature"]["sig"] = _sig.signature.hex()
    return blockData


def defaultMessages():
    """Map the ABI-encoded "empty" message to a list singleton.

    Used by the block producers to fall back to a default message when the
    mempool is empty:
        defaultMessage = eth_abi.encode(["address", "uint256", "bytes"],
                                        [ZERO_ADDRESS, 0, b""])
    """
    return [eth_abi.encode(["address", "uint256", "bytes"],
                           [constants.ZERO_ADDRESS, 0, b""])]


def _padSigComponent(value):
    """Left-pad an EVM signature r/s component to exactly 32 bytes (64 hex chars).

    Real ECDSA r/s values carry 61-64 hex chars (~9% are SHORTER than 64).
    bytesN values are left-aligned in the ABI: a short value that is not
    left-padded gets zero-padded on the RIGHT by eth_abi, so the contract
    would decode it as value * 256 — silently corrupted (the old inline
    code had exactly this bug for even-length-short hex, and crashed with
    ValueError for odd-length hex).  This mirrors bscPusher.bytes32Padding.
    """
    _s = value.replace("0x", "")
    return bytes.fromhex(_s.zfill(64))


def beaconBlockStruct(miner, block):
    """Encode a beacon block for the legacy ``sendL2Block`` contract.

    Returns the 12-field ``Beacon`` tuple consumed by the OLD StakeManager
    ``sendL2Block`` function (miner, nonce, messages, difficulty,
    miningTarget, timestamp, parent, proof, height, son, v, r, s).

    This shared version replaces the three byte-identical copies that used
    to live in RaptorBlockProducer (RaptorChain.py), blockProducer.py and
    raptormasternode.py.  It hardens the r/s encoding: the originals did
    ``bytes.fromhex(hex(r)[2:])`` which crashes on odd-length hex; this
    pads to a full byte first.

    NOTE: this is NOT the tuple shape bscPusher.py sends to the NEW
    ``pushBeacon`` contract (which adds parentTxRoot + relayerSigs) — that
    is a different, newer contract ABI and deliberately stays separate.
    """
    msgsList = list(eth_abi.decode(["bytes[]"], bytes.fromhex(block["messages"]))[0])
    _encodedParent = bytes.fromhex(block["parent"].replace("0x", ""))
    _encodedProof = bytes.fromhex(block["miningData"]["proof"].replace("0x", ""))
    _encodedSon = bytes.fromhex(block["son"].replace("0x", ""))
    _encodedSigR = _padSigComponent(hex(block["signature"]["r"]))
    _encodedSigS = _padSigComponent(hex(block["signature"]["s"]))
    return (miner, int(0), msgsList, 1, bytes.fromhex(constants.MAX_TARGET[2:]),
            int(block["timestamp"]), _encodedParent, _encodedProof, int(block["height"]),
            _encodedSon, int(block["signature"]["v"]), _encodedSigR, _encodedSigS)
