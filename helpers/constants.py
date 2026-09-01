"""Centralized constants for RaptorChain.

Previously these magic values were scattered as string/number literals
across RaptorChain.py and evmimplementation.py.  Importing from this
module keeps a single source of truth.
"""

# --- Addresses ---------------------------------------------------------------
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
BURN_ADDRESS = "0x000000000000000000000000000000000000dEaD"
CROSSCHAIN_ADDRESS = "0x0000000000000000000000000000000000000097"

# Precompiled contract addresses (EVM)
ECRECOVER_ADDRESS = "0x0000000000000000000000000000000000000001"
SHA256_ADDRESS = "0x0000000000000000000000000000000000000002"
RIPEMD160_ADDRESS = "0x0000000000000000000000000000000000000003"
BIO_MANAGER_ADDRESS = "0x0000000000000000000000000000000000000069"
DATAFEED_ADDRESS = "0x000000000000000000000000000000000000FEeD"

# 32-byte zero hash (used for empty parent/stateRoot/txRoot/etc.)
ZERO_HASH = "0x0000000000000000000000000000000000000000000000000000000000000000"

# --- Chain IDs ---------------------------------------------------------------
TESTNET_CHAIN_ID = 499597202514
MAINNET_CHAIN_ID = 1380996178

# BSC chain IDs (used by the bridge interface)
BSC_TESTNET_CHAIN_ID = 97
BSC_MAINNET_CHAIN_ID = 56

# --- Gas / economics ---------------------------------------------------------
DEFAULT_GAS_PRICE = 1000000000000000  # 0.001 RPTR or 1M gwei
DEFAULT_GAS_LIMIT = 69000              # legacy transfer gas limit
MN_COLLATERAL = 1000000000000000000000000  # 1,000,000 RPTR

# --- Software ----------------------------------------------------------------
NODE_VERSION = "1.8.0-mainnet-beta"

# --- Network ports -----------------------------------------------------------
TESTNET_PORT = 6969
MAINNET_PORT = 4242

# --- Networking --------------------------------------------------------------
MAX_PEERS = 200  # hard cap on the tracked peer table (see Node.askForMorePeers)


def chain_id(testnet: bool) -> int:
    """Return the RaptorChain chain ID for the given network mode."""
    return TESTNET_CHAIN_ID if testnet else MAINNET_CHAIN_ID


def bsc_chain_id(testnet: bool) -> int:
    """Return the BSC chain ID for the given network mode."""
    return BSC_TESTNET_CHAIN_ID if testnet else BSC_MAINNET_CHAIN_ID


def listen_port(testnet: bool) -> int:
    """Return the default listen port for the given network mode."""
    return TESTNET_PORT if testnet else MAINNET_PORT
