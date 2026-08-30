"""Shared utility helpers for RaptorChain.

These functions were previously duplicated (formatAddress appeared three
times in RaptorChain.py alone) or lived as module-level functions mixed
into the main file.
"""

import rich

from web3.auto import w3


def formatAddress(_addr):
    """Normalize an address to a checksummed hex string.

    Accepts either a 20-byte integer or a hex string.  This replaces the
    three identical copies that previously lived in Transaction,
    State.CallBlankTransaction and State.
    """
    if type(_addr) == int:
        return w3.to_checksum_address(_addr.to_bytes(20, "big"))
    return w3.to_checksum_address(_addr)


def printError(errorMessage):
    """Print an error message, falling back to plain print if rich fails."""
    try:
        rich.print(f"[red]{errorMessage}[/red]")
    except Exception:
        print(errorMessage)


def isNotComment(line):
    """Filter predicate for peers.txt lines.

    Returns True for lines that are neither comments (contain '#') nor the
    DISMISSCONFIG directive.
    """
    return (("#" not in line) and (line != "DISMISSCONFIG"))
