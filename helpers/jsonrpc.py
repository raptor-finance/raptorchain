"""JSON-RPC 2.0 envelope primitives.

Transport-agnostic pieces of the JSON-RPC protocol: the error object that
carries a spec-compliant error to the dispatcher, the request model, and the
helpers that turn a decoded request body into a validated request or an error
response.

Kept separate from helpers/web3rpc.py so the protocol layer (this file) does
not depend on the Ethereum method implementations, and so the error class can
be imported by the param validators without a forward reference.
"""

from typing import Any

import pydantic


# JSON-RPC 2.0 error codes
ERR_METHOD_NOT_FOUND = {"code": -32601, "message": "Method not found"}


class _RpcError(Exception):
    """Carries a JSON-RPC 2.0 error object to the dispatcher."""
    def __init__(self, errorObj):
        self.errorObj = errorObj


class Web3Body(pydantic.BaseModel):
    id: Any = None
    method: str
    params: list = pydantic.Field(default_factory=list)


def _isNotification(data: Web3Body):
    """True when a request is a notification, i.e. it OMITS the id member.

    JSON-RPC 2.0 draws a real distinction here: a request with no id member is
    a notification and gets no response, but a request with an explicit
    `"id": null` is an ordinary request whose id happens to be null and MUST be
    answered with a response echoing that null.  Web3Body.id defaults to None,
    so testing `data.id is None` conflated the two and answered HTTP 204 to an
    explicit null id — a strict client then waits for a reply that never comes.

    model_fields_set is what makes the distinction visible: it contains "id"
    only when the request actually supplied one.
    """
    return "id" not in data.model_fields_set


def _errorResponse(_id, _code, _message):
    """Build a JSON-RPC 2.0 error response object."""
    return {"id": _id, "jsonrpc": "2.0",
            "error": {"code": _code, "message": _message}}


def _bodyFromItem(_item):
    """Convert one decoded JSON-RPC request into a Web3Body.

    Returns a (body, errorResponse) pair; exactly one of the two is None.

    Validating each item here, rather than letting a pydantic model validate
    the whole Union[Web3Body, List[Web3Body]] body, is what stops one malformed
    member from destroying a batch: previously a single bad item made pydantic
    reject the ENTIRE array with HTTP 422, so every valid sibling request was
    silently discarded.  It also keeps the failure inside the JSON-RPC envelope
    instead of FastAPI's {"detail": [...]} payload, which a client cannot parse
    (it reads .error.code and finds nothing).

    Codes follow JSON-RPC 2.0: -32600 when the request shape itself is wrong
    (not an object, or no usable method), -32602 when only params are wrong.
    """
    if not isinstance(_item, dict):
        return None, _errorResponse(None, -32600,
                                    f"Invalid Request: expected an object, got {type(_item).__name__}")
    _id = _item.get("id")
    _method = _item.get("method")
    if not isinstance(_method, str):
        return None, _errorResponse(_id, -32600, "Invalid Request: method must be a string")
    _params = _item.get("params")
    if _params is None:
        # absent params and an explicit null both mean "no params"
        _params = []
    if not isinstance(_params, list):
        return None, _errorResponse(_id, -32602,
                                    f"Invalid params: expected an array, got {type(_params).__name__}")
    _fields = {"method": _method, "params": _params}
    # carry id ONLY when the request supplied it, so _isNotification can still
    # tell a notification from an explicit "id": null
    if "id" in _item:
        _fields["id"] = _item["id"]
    return Web3Body(**_fields), None
