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
# chainid -> RPC URL used by the node to pull cross-chain data
DATAFEED_RPCS = {
    56: "https://bsc-dataseed3.defibit.io",
    137: "https://poly.api.pocket.network",
    250: "https://fantom.drpc.org",
    1: "https://eth.drpc.org",
}

# --- BSC bridge RPCs (used by BSCInterface) ---------------------------------
# testnet / mainnet
BSC_RPC_TESTNET = "https://data-seed-prebsc-2-s1.binance.org:8545/"
BSC_RPC_MAINNET = "https://bsc.nodereal.io/"


def bsc_rpc(testnet: bool) -> str:
    """Return the BSC RPC URL for the given network mode."""
    return BSC_RPC_TESTNET if testnet else BSC_RPC_MAINNET