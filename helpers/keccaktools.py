"""Solidity-compatible packed hashing.

Owns ``packedKeccak`` -- the drop-in replacement for ``w3.solidity_keccak``
used for every hash this chain computes (txsRoot, beaconRoot, proofOfWork,
validatorSetHash, Account.calcHash, Masternode.hash, token storage slots,
txids and the wallet password digest).

Kept in its own module (rather than in ``helpers.utils``) because it is a
single cohesive, consensus-critical unit: the packing rules below decide
whether two nodes agree on a block, and the fallback rules exist to keep
behaviour identical to web3 on inputs the fast path cannot reproduce.  That is
worth isolating from the unrelated grab-bag of formatting, prompt and
transaction-signing helpers it used to sit next to.

Only ``packedKeccak`` is public.  Everything else is an implementation detail
of the packed encoder.
"""

from functools import lru_cache

from web3.auto import w3
from eth_utils import keccak
from hexbytes import HexBytes

_HEXDIGITS = frozenset("0123456789abcdef")


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

    Raised for: an odd-length or invalid hex string, a string without the "0x"
    prefix, a value of the wrong Python type, a negative or oversized uint/int,
    a non-bool for bool, a non-str for string, a non-list for ``T[]``, an
    address whose case does not match its EIP-55 checksum or whose prefix is not
    a lowercase "0x", a type name that is not exactly a supported one (including
    fixed-size arrays such as ``bytes32[2]``), an out-of-range type size
    (``uint``, ``uint7``, ``uint264``, ``bytes33``), a size that is in range but
    not spelled canonically (``uint08``, ``uint0256``, ``bytes010``, and
    non-ASCII digits that ``str.isdigit`` accepts), and a length mismatch
    between types and values.
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


def _wordSize(digits, maximum):
    """Byte width from the digits of a uint/int type ("256" -> 32).

    Only sizes web3 RECOGNISES are accepted, which means both an ABI-legal
    width (8..maximum in steps of 8) and its canonical spelling: web3's
    ``is_recognized_type`` matches the literal names uint8..uint256, so "uint08"
    is an unrecognized type to web3 rather than uint8.  Anything else -- a
    size-less "uint", "uint7", "uint2_5", "uint08", "uint0256" -- is deferred
    to web3, which either rejects the type or produces an encoding that cannot
    be reproduced by whole-byte padding.
    """
    if not digits.isdigit():
        raise _NeedsWeb3Fallback()
    _bits = int(digits)
    if not (8 <= _bits <= maximum) or _bits % 8:
        raise _NeedsWeb3Fallback()
    # str.isdigit() is true for non-ASCII digits ("\u0668"), which int() parses
    # happily; comparing against the canonical spelling rejects those too, since
    # web3 knows only the ASCII names.
    if digits != str(_bits):
        raise _NeedsWeb3Fallback()
    return _bits // 8


@lru_cache(maxsize=1 << 16)
def _isChecksumAddress(value):
    """True iff web3's validate_address would accept this exact string.

    web3 requires ``value == to_checksum_address(value)`` (EIP-55), so an
    address that is all-lowercase *and contains letters* is REJECTED, as is a
    mixed-case address whose case pattern does not match the digest.  Anything
    less strict would let packedKeccak succeed on input web3 refuses -- the
    same direction of bug as the CREATE-nonce crash -- so it is checked here.

    The prefix is validated too, and it must be a lowercase "0x".  Slicing
    ``value[2:]`` and checking only those 40 characters accepts ANY two leading
    characters ("0X...", "ZZ...", "12..."), and an all-digit tail contains no
    letters, so the case comparison below cannot reject it either.  web3 refuses
    all of those: ``is_hex_address`` requires ``is_0x_prefixed``, and even "0X"
    fails its final equality check because ``to_checksum_address`` emits a
    lowercase "0x".

    eth_utils computes the digest over the LOWERCASE hex text (without "0x")
    and uppercases a nibble when the corresponding digest nibble is > 7.

    Cached because the same addresses are hashed repeatedly (Account.calcHash
    runs once per affected account per transaction) and the digest is the only
    real cost.  Valid addresses are bounded by the chain's address space; the
    cache is capped so a flood of distinct invalid addresses cannot grow it
    without bound.
    """
    if not value.startswith("0x"):
        # not a formality: without this ANY two leading characters pass, so
        # packedKeccak would hash an "address" web3 rejects outright
        return False
    _hex = value[2:]
    if len(_hex) != 40:
        return False
    _lower = _hex.lower()
    try:
        _digest = keccak(_lower.encode("ascii")).hex()
    except UnicodeEncodeError:
        return False
    for _i, _char in enumerate(_lower):
        # a char that is not a hex digit has no lowercase->uppercase mapping,
        # so the comparison below would wrongly accept it
        if _char not in _HEXDIGITS:
            return False
        _expected = _char.upper() if int(_digest[_i], 16) > 7 else _char
        if _hex[_i] != _expected:
            return False
    return True


@lru_cache(maxsize=1024)
def _parseType(abiType):
    """Resolve a type name to ("kind", detail), or defer to web3.

    Parsing is separated from encoding on purpose: the whole type is resolved
    BEFORE any value is looked at, so an invalid element type is still caught
    when the array is EMPTY.  Deferring that check until elements are encoded
    let `packedKeccak(["[]"], [[]])` produce a hash where web3 raises
    ParseError, because an empty array yields no element to encode.

    Type names are matched EXACTLY.  A prefix test would silently read the
    fixed-size array "bytes32[2]" as the scalar type "bytes" and encode a bytes
    value as though the [2] were not there -- which is what an earlier version
    did whenever the value happened to be bytes rather than a list.

    Cached because a type string is re-parsed on EVERY call while only ever
    changing with the call site: the set of names the chain uses is a fixed
    handful ("bytes32", "bytes32[]", "address", "uint256", "string",
    "bytes"), and parsing one costs ~400 ns against the ~85 ns the
    accept-checks above cost.  The saving is per CALL, not per element, so a
    16 000-element ``bytes32[]`` gains once either way -- but a txid or a token
    storage slot, hashed in a tight loop, gains every time.  That makes the
    total a net win over having no accept-checks at all, rather than merely
    offsetting them.

    Cache misses are bounded (maxsize, LRU) and exceptions are NOT cached:
    lru_cache only memoises returns, so an unrecognized name re-parses and
    still defers to web3 on every call.  Deeply nested arrays ("bytes32[][]")
    bake in one entry per level, which is what maxsize bounds.  A non-string
    argument now raises TypeError at the cache lookup instead of AttributeError
    inside the body; packedKeccak catches both and defers, so web3 still raises
    whatever it raised before.
    """
    if abiType.endswith("[]"):
        return ("array", _parseType(abiType[:-2]))
    if abiType == "address":
        return ("address", 0)
    if abiType == "bool":
        return ("bool", 0)
    if abiType == "string":
        return ("string", 0)
    if abiType == "bytes":
        return ("bytes", 0)
    if abiType.startswith("bytes"):
        # bytesN must be N in the ABI-legal range; "bytes32[2]" arrives here
        # as "32[2]", which is not a digit run and so defers to web3
        _size = abiType[5:]
        if not _size.isdigit():
            raise _NeedsWeb3Fallback()
        _bytes = int(_size)
        # same rule as _wordSize: web3 knows bytes1..bytes32 by literal name, so
        # "bytes08" is an unrecognized type to it, not bytes8
        if not (1 <= _bytes <= 32) or _size != str(_bytes):
            raise _NeedsWeb3Fallback()
        return ("bytes", 0)
    if abiType.startswith("uint"):
        return ("uint", _wordSize(abiType[4:], 256))
    if abiType.startswith("int"):
        return ("int", _wordSize(abiType[3:], 256))
    raise _NeedsWeb3Fallback()


def _packedEncode(parsed, value, forceWord=False):
    """Encode one argument exactly as web3's hex_encode_abi_type does.

    ``parsed`` is the result of _parseType.  ``forceWord`` mirrors the
    force_size=256 web3 applies to the elements of an array, which widens
    address/uint/int/bool to a full 32-byte word but is ignored for the
    byte-ish types.

    A value that does not fit its type, or is of the wrong Python type, defers
    to web3 (see _NeedsWeb3Fallback) -- web3 then either produces its usual
    result or raises its usual error, so behaviour is unchanged either way.
    """
    _kind, _detail = parsed
    if _kind == "array":
        if not isinstance(value, (list, tuple)):
            raise _NeedsWeb3Fallback()
        return b"".join(_packedEncode(_detail, _item, True) for _item in value)
    if _kind == "address":
        if not isinstance(value, str) or not _isChecksumAddress(value):
            raise _NeedsWeb3Fallback()
        _raw = bytes.fromhex(value[2:])
        return _raw.rjust(32, b"\x00") if forceWord else _raw
    if _kind == "bool":
        # web3's is_boolean accepts ONLY True/False; an int is rejected
        if not isinstance(value, bool):
            raise _NeedsWeb3Fallback()
        return (1 if value else 0).to_bytes(32 if forceWord else 1, "big")
    if _kind == "uint":
        _size = 32 if forceWord else _detail
        # web3's is_integer excludes bool, and rejects negatives
        if not isinstance(value, int) or isinstance(value, bool):
            raise _NeedsWeb3Fallback()
        if value < 0 or value >= (1 << (_size * 8)):
            # web3 emits a LONGER hex string rather than truncating, and
            # rejects negatives outright: both need web3's own handling
            raise _NeedsWeb3Fallback()
        return value.to_bytes(_size, "big")
    if _kind == "int":
        _size = 32 if forceWord else _detail
        if not isinstance(value, int) or isinstance(value, bool):
            raise _NeedsWeb3Fallback()
        if not (-(1 << (_size * 8 - 1)) <= value < (1 << (_size * 8 - 1))):
            raise _NeedsWeb3Fallback()
        return (value & ((1 << (_size * 8)) - 1)).to_bytes(_size, "big")
    if _kind == "bytes":
        return _packedBytes(value)
    if _kind == "string":
        if not isinstance(value, str):
            # web3's to_hex(text=...) only accepts text for a string argument
            raise _NeedsWeb3Fallback()
        return value.encode()
    raise _NeedsWeb3Fallback()


def packedKeccak(abiTypes, values):
    """Byte-identical, much faster replacement for ``w3.solidity_keccak``.

    ``w3.solidity_keccak`` hex-encodes every argument, concatenates the hex
    strings and then decodes the result back to bytes inside
    ``w3.keccak(hexstr=...)``, re-validating each value on the way.  That is
    what dominates its cost, and the cost scales with the input: measured on
    the shapes this project uses, a 16 000-element ``bytes32[]`` took ~449 ms
    through web3 against ~16 ms here.

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
    ``w3.solidity_keccak``, or raises the same error it raises.  Anything the
    fast path cannot reproduce with certainty is handed to web3 itself rather
    than guessed at -- see _NeedsWeb3Fallback for why (CREATE/CREATE2 put the
    odd-length contract nonce ``hex(1)`` == "0x1" into Account.sent, which is
    real committed state).  "The same error" covers web3's ACCEPTANCE rules, not
    just its bytes: inputs its validators reject (a non-canonical type width
    such as ``uint08``, an address without a lowercase "0x") defer as well, so
    the fast path can never hash something web3 would have refused.

    The fallback is ``w3.solidity_keccak`` on the module-level ``web3.auto``
    instance imported above.  web3 runs address arguments through
    ``abi_ens_resolver`` -- the one normalizer in ``solidity_keccak`` that
    depends on WHICH ``Web3`` object is used -- so an ENS name ("name.eth")
    passed as an address argument is resolved, or fails, against the auto
    instance rather than a caller's connected one.  ENS names are not checksum
    addresses, so they always take the fallback, and every other input is
    instance-independent; a caller that hashes ENS names must call its own w3.

    Measured end-to-end on this codebase: calcStateRoot ~27-38x, txsRoot ~27-31x,
    validatorSetHash ~21-37x, Account.calcHash ~10-32x, playTransaction ~8-22x.
    ``tests/test_packed_keccak.py`` pins both the value equality and the fact
    that every production shape actually takes the fast path (a fallback would
    be correct but silently slow).
    """
    try:
        # length is checked by web3 too; doing it here keeps the fast path
        # from zipping mismatched lists into a silently short hash
        if len(abiTypes) != len(values):
            raise _NeedsWeb3Fallback()
        # types are resolved BEFORE any value is read, so an invalid element
        # type is rejected even when its array is empty
        _parsed = [_parseType(_abiType) for _abiType in abiTypes]
        _packed = b"".join(
            _packedEncode(_parsedType, _value)
            for _parsedType, _value in zip(_parsed, values)
        )
    except (_NeedsWeb3Fallback, TypeError, ValueError, AttributeError, OverflowError):
        # web3 reproduces the exact historical behaviour for these, including
        # raising its own exception for the inputs it always rejected
        return w3.solidity_keccak(abiTypes, values)
    return HexBytes(keccak(_packed))
