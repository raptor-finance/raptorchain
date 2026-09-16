"""Centralized chain RPC endpoints for RaptorChain.

Previously these URLs were hardcoded as string literals inside
RaptorChain.py (BSCInterface / DataFeedInterface).  Importing from this
module keeps a single source of truth for the external chain RPCs the
node talks to (BSC, Polygon, Fantom, Ethereum).
"""

# --- RaptorChain's own public RPC -------------------------------------------
PUBLIC_RPC = "https://rpc.raptorchain.io/"
PUBLIC_RPC_TESTNET = "https://rpc-testnet.raptorchain.io/"

# --- External chain RPCs (used by DataFeedInterface) ------------------------
# chainid -> RPC URL used by the node to pull cross-chain data.
# This dict is the SINGLE source of truth for chain RPCs: BSCInterface also
# reads its BSC entries (56 = mainnet, 97 = testnet) instead of keeping its
# own copies.
DATAFEED_RPCS = {
    56: "https://rpc-bsc.blockmachine.io",
    97: "https://data-seed-prebsc-2-s1.binance.org:8545/",
    137: "https://poly.api.pocket.network",
    250: "https://fantom.drpc.org",
    1: "https://rpc-eth.blockmachine.io",
}

# --- BSC bridge RPCs (used by BSCInterface) ---------------------------------
# Kept as aliases into DATAFEED_RPCS so BSCInterface reads the same dict.
BSC_RPC_TESTNET = DATAFEED_RPCS[97]
BSC_RPC_MAINNET = DATAFEED_RPCS[56]


def bsc_rpc(testnet: bool) -> str:
    """Return the BSC RPC URL for the given network mode."""
    return BSC_RPC_TESTNET if testnet else BSC_RPC_MAINNET