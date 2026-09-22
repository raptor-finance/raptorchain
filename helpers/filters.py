"""In-memory polling-filter registry for the JSON-RPC endpoint.

Ethereum's polling-filter API (eth_newFilter / eth_getFilterChanges / ...) is
stateful, so the registry lives here rather than in the method handlers.  It is
kept for the lifetime of the process: filters are ephemeral by design (geth
expires idle ones too), so losing them on a restart is spec-consistent rather
than a defect.

Cursors are TX-ORDER indices, like every other block-number answer on the
/web3 endpoint: a synthetic block holds exactly one transaction, and its hash
IS that transaction's hash.

This module deliberately does NOT import the node.  Everything that needs node
state takes it as an argument, which keeps the registry testable in isolation
and avoids a circular import with helpers/web3rpc.py.
"""

import secrets
import threading
import time

from .jsonrpc import _RpcError

FILTER_TTL_SECONDS = 300   # idle expiry, swept opportunistically on each call
MAX_FILTERS = 1024         # hard cap so a public endpoint cannot be flooded

FILTER_KIND_BLOCK = "block"
FILTER_KIND_PENDING = "pending"
FILTER_KIND_LOG = "log"

# A plain (non-reentrant) Lock is enough because no locked helper ever calls
# back into another locking helper: _sweepFilters/_newFilter/_requireFilter all
# document that the caller must already hold it, and the handlers hold it
# across the whole read-modify-write of a filter's cursor.
_filtersLock = threading.Lock()
_filters = {}


def _sweepFilters():
    """Drop filters idle past FILTER_TTL_SECONDS.  Caller must hold _filtersLock.

    Uses time.monotonic() rather than time.time(): a TTL measured against the
    wall clock would let an NTP step retroactively keep every filter alive (or
    expire them all at once).
    """
    _now = time.monotonic()
    _stale = [_filterId for _filterId, _filter in _filters.items()
              if _now - _filter["lastPolledAt"] > FILTER_TTL_SECONDS]
    for _filterId in _stale:
        del _filters[_filterId]


def _requireFilter(_filterId):
    """Return a live filter, else raise.  Caller must hold _filtersLock.

    The error code matters: clients read -32601 as "this node has no filter
    support" and give up permanently, whereas -32000 is the standard
    "filter not found / expired" signal they are expected to recover from by
    creating a new filter.  Reporting -32601 here would defeat the whole
    point of implementing the filter family.
    """
    if not isinstance(_filterId, str):
        raise _RpcError({"code": -32602, "message": f"Invalid filter id: {_filterId!r}"})
    _sweepFilters()
    _filter = _filters.get(_filterId)
    if _filter is None:
        raise _RpcError({"code": -32000, "message": "filter not found"})
    return _filter


def _newFilter(_kind, _cursor, _endIndex=None, _startIndex=None, _addrs=None, _topicsFilter=None):
    """Register a filter and return its id.  Caller must hold _filtersLock."""
    _sweepFilters()
    if len(_filters) >= MAX_FILTERS:
        raise _RpcError({"code": -32000,
                         "message": f"Too many active filters (limit {MAX_FILTERS}); "
                                    "release unused ones with eth_uninstallFilter"})
    _filterId = "0x" + secrets.token_hex(16)
    _filters[_filterId] = {"kind": _kind, "cursor": _cursor, "endIndex": _endIndex,
                           "startIndex": _startIndex, "addrs": _addrs,
                           "topics": _topicsFilter, "lastPolledAt": time.monotonic()}
    return _filterId


def _filterWindow(_filter, _txCount):
    """Return the [start, end) tx-order window a filter currently covers.

    endIndex None means the filter keeps tracking new blocks; an explicit
    endIndex bounds it permanently.
    """
    _start = _filter["cursor"]
    _end = _txCount if _filter["endIndex"] is None else min(_filter["endIndex"], _txCount)
    return (_start if _start <= _end else _end), _end
