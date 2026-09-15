"""Shared utility helpers for RaptorChain.

These functions were previously duplicated (formatAddress appeared three
times in RaptorChain.py alone) or lived as module-level functions mixed
into the main file.
"""

import sys
import time

import rich

import eth_abi
from web3.auto import w3
from eth_account.messages import encode_defunct
from eth_utils import keccak
from hexbytes import HexBytes

from . import constants


def formatAddress(_addr):
    """Normalize an address to a checksummed hex string.

    Accepts either a 20-byte integer or a hex string.  This replaces the
    three identical copies that previously lived in Transaction,
    State.CallBlankTransaction and State.
    """
    if type(_addr) == int:
        return w3.to_checksum_address(_addr.to_bytes(20, "big"))
    return w3.to_checksum_address(_addr)


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


class _NeedsWeb3Fallback(Exception):
    """Internal signal: this call must be encoded by w3.solidity_keccak itself.

    The fast path encodes each argument independently, which is only equivalent
    to web3 when EVERY argument contributes whole bytes.  web3 works in hex
    instead: it hex-encodes each argument, concatenates the hex STRINGS, and
    only then turns the joined string into bytes -- left-padding a single nibble
    if the total length is odd.  So an argument with an odd number of hex digits
    shifts every following nibble:

        ["bytes32","bytes32"], ["0x1","0x2"]  ->  keccak(b"\\x12")
                                             NOT keccak(b"\\x01\\x02")

    That is reachable in production, not a theoretical edge case: CREATE and
    CREATE2 append the contract nonce as ``hex(_nonce)`` ("0x0", "0x1", ...)
    to Account.sent, and Account.calcHash hashes ``sent[1:]`` as bytes32[].
    The first nonce is "0x1", because ``_nonce = len(sent)`` and sent is seeded
    with initTxID.  Those values are committed chain state, so they must hash
    exactly as they always did.

    Rather than re-deriving web3's nibble arithmetic (and getting it subtly
    wrong), anything the fast path cannot encode with certainty raises this and
    packedKeccak delegates to web3.  The result is then identical by
    construction.  Ordinary calls never reach the fallback, so its cost is
    irrelevant; correctness on the odd cases is what matters.
    """


def _packedBytes(value):
    """The raw bytes a packed bytes/bytesN argument contributes.

    Mirrors web3's hex_encode_abi_type for the byte-ish types: bytes are used
    verbatim (web3 hex-encodes and re-decodes them), and a hex string is
    decoded.  Note that bytesN is NOT padded to N bytes -- web3 emits
    encode_hex(value) whatever its length, which is why a 31-byte value
    contributes 31 bytes.

    Anything that cannot be reproduced exactly is deferred to web3 via
    _NeedsWeb3Fallback instead of raising, so this can never reject (or
    silently alter) an input web3 would have accepted.
    """
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if not isinstance(value, str):
        raise _NeedsWeb3Fallback()
    if not value.startswith("0x"):
        # web3's validate_abi_value rejects this; let web3 raise its own error
        raise _NeedsWeb3Fallback()
    _hex = value[2:]
    if len(_hex) % 2:
        # odd nibble count: web3 pads the JOINED string, so per-argument
        # padding here would produce a different hash (see _NeedsWeb3Fallback)
        raise _NeedsWeb3Fallback()
    try:
        return bytes.fromhex(_hex)
    except ValueError:
        # not valid hex at all: defer so web3 raises exactly what it always did
        raise _NeedsWeb3Fallback()


def _packedWordSize(abiType, prefixLength):
    """Byte width of a uint/int type ("uint256" -> 32).

    A size-less "uint"/"int" is deferred to web3, which rejects it, so a typo
    fails the same way it always did rather than hashing differently.
    """
    _digits = abiType[prefixLength:]
    if not _digits:
        raise _NeedsWeb3Fallback()
    try:
        return int(_digits) // 8
    except ValueError:
        raise _NeedsWeb3Fallback()


def _packedEncode(abiType, value, forceWord=False):
    """Encode one argument exactly as web3's hex_encode_abi_type does.

    ``forceWord`` mirrors the force_size=256 web3 applies to the elements of an
    array, which widens address/uint/int/bool to a full 32-byte word but is
    ignored for the byte-ish types.

    A value that does not fit its type, a type this does not implement, or a
    value of the wrong Python type all defer to web3 (see
    _NeedsWeb3Fallback) -- web3 then either produces its usual result or raises
    its usual error, so behaviour is unchanged either way.
    """
    if abiType.endswith("[]"):
        if not isinstance(value, (list, tuple)):
            # web3 requires a list-like for an array type
            raise _NeedsWeb3Fallback()
        return b"".join(_packedEncode(abiType[:-2], _item, True) for _item in value)
    if abiType == "address":
        # web3 validates strictly: exactly "0x" + 40 hex chars.  Shorter,
        # longer, unprefixed or non-hex values are rejected (or sent to ENS
        # resolution), so anything else must be left to web3.
        if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
            raise _NeedsWeb3Fallback()
        try:
            _raw = bytes.fromhex(value[2:])
        except ValueError:
            raise _NeedsWeb3Fallback()
        return _raw.rjust(32, b"\x00") if forceWord else _raw
    if abiType == "bool":
        # web3's is_boolean accepts ONLY True/False; an int is rejected
        if not isinstance(value, bool):
            raise _NeedsWeb3Fallback()
        return (1 if value else 0).to_bytes(32 if forceWord else 1, "big")
    if abiType.startswith("uint"):
        _size = 32 if forceWord else _packedWordSize(abiType, 4)
        # web3's is_integer excludes bool, and rejects negatives
        if not isinstance(value, int) or isinstance(value, bool):
            raise _NeedsWeb3Fallback()
        if value < 0 or value >= (1 << (_size * 8)):
            # web3 emits a LONGER hex string rather than truncating, and
            # rejects negatives outright: both need web3's own handling
            raise _NeedsWeb3Fallback()
        return value.to_bytes(_size, "big")
    if abiType.startswith("int"):
        _size = 32 if forceWord else _packedWordSize(abiType, 3)
        if not isinstance(value, int) or isinstance(value, bool):
            raise _NeedsWeb3Fallback()
        if not (-(1 << (_size * 8 - 1)) <= value < (1 << (_size * 8 - 1))):
            raise _NeedsWeb3Fallback()
        return (value & ((1 << (_size * 8)) - 1)).to_bytes(_size, "big")
    if abiType.startswith("bytes"):
        return _packedBytes(value)
    if abiType == "string":
        if not isinstance(value, str):
            # web3's to_hex(text=...) only accepts text for a string argument
            raise _NeedsWeb3Fallback()
        return value.encode()
    raise _NeedsWeb3Fallback()


def packedKeccak(abiTypes, values):
    """Byte-identical, much faster replacement for ``w3.solidity_keccak``.

    ``w3.solidity_keccak`` hex-encodes every argument, concatenates the hex
    strings and then decodes the result back to bytes inside
    ``w3.keccak(hexstr=...)``.  That hex round trip dominates its cost, and the
    cost scales with the input: measured on the shapes this project uses, a
    16 000-element ``bytes32[]`` took 391 ms through web3 against 4.6 ms for the
    equivalent byte concatenation (~85x), which is what made ``calcStateRoot``
    the single hottest path in a transaction.

    This builds the same bytes directly, reproducing web3's packing rules
    (Solidity "packed" semantics -- no length prefixes, no word alignment):

      - ``address``                      -> 20 bytes (32 as an array element)
      - ``uintN`` / ``intN`` / ``bool``  -> N/8 bytes, left-zero-padded
      - ``bytesN``                       -> the bytes as given, NOT padded to N
      - ``bytes`` / ``string``           -> raw bytes, no length prefix
      - ``T[]``                          -> concatenation of packed elements

    Returns HexBytes exactly like ``w3.solidity_keccak``, so ``.hex()`` keeps
    its "0x" prefix and call sites need no other change.

    Correctness contract: for EVERY input this returns the same bytes as
    ``w3.solidity_keccak``, or raises the same error it raises.  Any argument
    the fast path cannot encode with certainty (odd-length hex, a negative
    unsigned value, an exotic type) is handed to web3 itself rather than
    guessed at -- see _NeedsWeb3Fallback, which documents the CREATE/CREATE2
    contract nonce (``hex(1)`` == "0x1") that made this necessary.

    ``tests/test_packed_keccak.py`` asserts that equality, including for the
    degenerate shapes.
    """
    try:
        # length is checked by web3 too; doing it here keeps the fast path
        # from zipping mismatched lists into a silently short hash
        if len(abiTypes) != len(values):
            raise _NeedsWeb3Fallback()
        _packed = b"".join(
            _packedEncode(_abiType, _value)
            for _abiType, _value in zip(abiTypes, values)
        )
    except (_NeedsWeb3Fallback, TypeError, ValueError, AttributeError, OverflowError):
        # web3 reproduces the exact historical behaviour for these, including
        # raising its own exception for the inputs it always rejected
        return w3.solidity_keccak(abiTypes, values)
    return HexBytes(keccak(_packed))


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
