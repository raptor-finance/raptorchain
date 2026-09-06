"""Shared utility helpers for RaptorChain.

These functions were previously duplicated (formatAddress appeared three
times in RaptorChain.py alone) or lived as module-level functions mixed
into the main file.
"""

import time

import rich

import eth_abi
from web3.auto import w3
from eth_account.messages import encode_defunct


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
            "hash": w3.solidity_keccak(["string"], [txdata]).hex()}


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
    bRoot = w3.solidity_keccak(
        ["bytes32", "uint256", "bytes32", "bytes32", "address"],
        [parent, int(timestamp), messagesHash, _txRoot, miner]).hex()
    return w3.solidity_keccak(["bytes32", "uint256"], [bRoot, int(0)]).hex()


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
                                "miningTarget": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                                "proof": None},
                 "height": height, "parent": parent,
                 "messages": messagesHex,
                 "timestamp": (int(time.time()) if timestamp is None else int(timestamp)),
                 "son": "0x" + ("0" * 64),
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
                           ["0x0000000000000000000000000000000000000000", 0, b""])]


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
    return (miner, int(0), msgsList, 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"),
            int(block["timestamp"]), _encodedParent, _encodedProof, int(block["height"]),
            _encodedSon, int(block["signature"]["v"]), _encodedSigR, _encodedSigS)
