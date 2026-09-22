"""JSON-RPC parameter validation helpers.

Every helper here raises `_RpcError(-32602 invalid params)` on bad input, so a
malformed request produces a spec-compliant JSON-RPC error instead of an opaque
-32603 "Internal error" from an IndexError/TypeError deep in a handler.

These are deliberately free of any node dependency: they validate and coerce
the *request*, nothing else.  Anything that needs node state (resolving
"latest", for instance) belongs in the caller.
"""

from web3.auto import w3

from .jsonrpc import _RpcError


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


def _requireQuantity(value, what):
    """Validate a JSON-RPC quantity member (value/gas/gasprice), else -32602.

    Accepts an int, or a non-empty decimal or 0x-hex string — the same forms
    CallBlankTransaction coerces.  Anything else (notably the empty string,
    which int() cannot parse) previously reached int() and escaped as -32603.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value:
        try:
            int(value, 16) if "0x" in value else int(value, 10)
            return value
        except ValueError:
            pass
    raise _RpcError({"code": -32602, "message": f"Invalid {what}: {value!r}"})


def _parseIndex(_value, _what, _reprString=True):
    """Parse a JSON-RPC quantity index (hex string or int), else -32602.

    Bools and floats are rejected even though Python would happily coerce
    them: neither is a legal JSON-RPC quantity.

    _reprString controls how a malformed STRING is rendered in the message.
    The block-param and storage-slot parsers have always reported the bare
    value ("Invalid block param: nope") while the index parsers use repr()
    ("Invalid transaction index: 'nope'"), so the flag keeps both messages
    byte-identical to what clients already receive.
    """
    if isinstance(_value, bool) or not isinstance(_value, (int, str)):
        raise _RpcError({"code": -32602, "message": f"Invalid {_what}: {_value!r}"})
    if isinstance(_value, int):
        return _value
    _stripped = _value[2:] if _value.startswith("0x") else _value
    try:
        return int(_stripped, 16)
    except ValueError:
        _shown = repr(_value) if _reprString else _value
        raise _RpcError({"code": -32602, "message": f"Invalid {_what}: {_shown}"})


def _looksLikeHash(_value):
    """True for a 32-byte 0x-prefixed hex string (an Ethereum hash)."""
    return isinstance(_value, str) and _value.startswith("0x") and len(_value) == 66


def _requireCallObject(data):
    """Validate params[0] of eth_call/eth_estimateGas and return it cleaned.

    Without this, a non-object argument (e.g. ["nope"]) reached
    CallBlankTransaction's `call.get(...)` and escaped as an unhandled
    AttributeError, which the dispatcher reported as -32603 "Internal error" —
    telling the client the node was broken when the request was malformed.

    Address- and quantity-typed members are checked here too, because they are
    converted (to_checksum_address / int(...)) before the EVM ever runs, so a
    bad value there produced the same misleading -32603.

    `data` is deliberately NOT validated: CallBlankTransaction already wraps its
    parsing in try/except and falls back to b"", so it cannot raise.

    Returns a COPY with null-valued members removed.  That matters: the node
    reads these with `call.get(key, DEFAULT)`, which yields None — not the
    default — when the key is present with a null value, and None then crashed
    address and gas coercion ("Exactly one of the passed values can be
    specified", "int() can't convert non-string").  Dropping nulls makes an
    explicit null behave exactly like an absent member, which is what a client
    sending null means by it.
    """
    _requireParams(data, 1)
    _call = data.params[0]
    if not isinstance(_call, dict):
        raise _RpcError({"code": -32602,
                         "message": f"Invalid call object: expected an object, got {type(_call).__name__}"})
    _clean = {_k: _v for _k, _v in _call.items() if _v is not None}
    for _key in ("from", "to"):
        if _key in _clean:
            _requireAddress(_clean[_key])
    for _key in ("value", "gas", "gasprice"):
        if _key in _clean:
            _requireQuantity(_clean[_key], _key)
    return _clean


# EIP-2718 typed-transaction envelopes this node cannot replay.  RaptorChain
# only supports legacy (pre-EIP-2718) transactions: typed envelopes start with
# a type byte in 0x00-0x7f, while legacy transactions are RLP lists and always
# start at 0xc0 or above.
_TX_TYPE_NAMES = {
    0x01: "EIP-2930 access-list",
    0x02: "EIP-1559 fee-market",
    0x03: "EIP-4844 blob",
    0x04: "EIP-7702 set-code",
}


def _rejectUnsupportedRawTx(rawTx):
    """Reject raw transactions this node cannot replay, up front.

    Without this, an EIP-1559 / EIP-2930 payload reaches the legacy-only RLP
    decoder (crypto/eth_decoder.py) and blows up with a raw RLP exception that
    the dispatcher reports as -32603 "Internal error" — which tells the client
    the *node* is broken, when in fact it sent a transaction type this chain
    does not support.  Raising -32602 here makes it an explicit, client-side
    rejection with an actionable message.
    """
    if not isinstance(rawTx, str):
        raise _RpcError({"code": -32602,
                         "message": f"Invalid raw transaction: expected a hex string, got {type(rawTx).__name__}"})
    _hexStr = rawTx[2:] if rawTx.startswith("0x") else rawTx
    if not _hexStr:
        raise _RpcError({"code": -32602, "message": "Invalid raw transaction: empty"})
    # Validate the WHOLE payload, not just the leading byte: the decoder feeds
    # this to bytes.fromhex(), so a bad character or odd length anywhere would
    # otherwise escape as a -32603 internal error.
    try:
        _rawBytes = bytes.fromhex(_hexStr)
    except ValueError:
        raise _RpcError({"code": -32602, "message": f"Invalid raw transaction: not valid hex ({rawTx[:16]!r}...)"})
    if not _rawBytes:
        raise _RpcError({"code": -32602, "message": "Invalid raw transaction: empty"})
    _firstByte = _rawBytes[0]
    if _firstByte <= 0x7f:
        _name = _TX_TYPE_NAMES.get(_firstByte)
        _label = f"0x{_firstByte:02x}" + (f" ({_name})" if _name else "")
        raise _RpcError({"code": -32602,
                         "message": f"Unsupported transaction type {_label}: this node accepts legacy pre-EIP-2718 transactions only"})
