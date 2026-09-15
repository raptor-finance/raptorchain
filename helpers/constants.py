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

# Maximum PoW mining target (difficulty-1): block hashes must be below it
MAX_TARGET = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

# Empty 256-byte logs bloom (hex), as served in receipts / block headers
ZERO_BLOOM = "0x" + ("00" * 256)

# --- EVM word arithmetic -----------------------------------------------------
# These MUST be module-level names rather than inline literals.  CPython's AST
# optimizer deliberately does NOT constant-fold `**`, `/` or `//`, so an
# expression such as `x % (2**256)` re-runs a full bignum exponentiation on
# EVERY evaluation -- and the arithmetic opcodes evaluate it once per call, in
# the hottest loop on the chain.  Verified with `dis`: `x % (2**256)` compiles
# to `LOAD_CONST 2; LOAD_CONST 256; BINARY_OP **; BINARY_OP %`.  Measured:
# `int(int(a+b) % (2**256))` = 147.5ns vs `(a+b) % UINT256_MODULUS` = 36.3ns.
UINT256_MODULUS = 2 ** 256          # wrap-around modulus for 256-bit unsigned math
UINT256_MAX = UINT256_MODULUS - 1   # largest uint256 (== int(MAX_TARGET, 16))
INT256_SIGN_BIT = 2 ** 255          # at or above this, a word is negative as int256

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

# --- Timeouts (seconds) ------------------------------------------------------
# Without these, a dependency that accepts a TCP connection but never replies
# blocks the caller *indefinitely* (no socket-level default exists). That turns
# a degraded RPC into a hung node: startup never completes, or the background
# loop stops without a word.  A bounded failure is always preferable, because
# the surrounding code already handles exceptions (it does not handle hangs).
#
# Note: web3's retry middleware issues up to 3 attempts with backoff, so the
# worst-case wall time is a few multiples of HTTP_TIMEOUT_SECONDS.
HTTP_TIMEOUT_SECONDS = 30        # web3 JSON-RPC providers (BSC + datafeed)
PEER_TIMEOUT_SECONDS = 30        # requests.get() to RaptorChain peers


def chain_id(testnet: bool) -> int:
    """Return the RaptorChain chain ID for the given network mode."""
    return TESTNET_CHAIN_ID if testnet else MAINNET_CHAIN_ID


def bsc_chain_id(testnet: bool) -> int:
    """Return the BSC chain ID for the given network mode."""
    return BSC_TESTNET_CHAIN_ID if testnet else BSC_MAINNET_CHAIN_ID


def listen_port(testnet: bool) -> int:
    """Return the default listen port for the given network mode."""
    return TESTNET_PORT if testnet else MAINNET_PORT
