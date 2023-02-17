# Cross-Chain
RaptorChain allows communications with other blockchains.
Communication occurs by 2 channels :
- raptorchain to others : cross-chain messages (thru beacon chain)
- others to raptorchain : cross-chain data feed (outside of beacon chain)

## Cross-chain messages
Cross-chain messages are the way to send messages from RaptorChain to other chains.

### Encoding
Low-level system messages are encoded using ethereum ABI in the following way `(address to, uint256 chainid, bytes payload)`
Since they don't contain a `from` field (they weren't planned to carry user messages), payload is used to wrap higher-level messages (the ones user can send), 
which are encoded in the following way `(address from, address to, uint256 gasLimit, bytes data)`

### Sending a cross-chain message
You can send a cross-chain message by calling the precompile at `0x000000000000000000000000000000000000FEeD` with params `crossChainCall(chainid, to, gas, data)`

Solidity interface is available in contracts/raptorchain/dataFeedInterface.sol

It will create a cross-chain message and add it to mempool.

Please note that message propagation isn't instant.

### Propagation
Cross-chain message propagation could take time time.

Basically, it needs message to be included in a beacon block (~10mins), and the beacon block to be forwarded to destination chain (which ITSELF requires it to match a number of validator confirmations/sigs)

## Cross-chain data feeds
Other chains to RaptorChain communication goes through data feeds, which are basically a way to pass data to raptorchain.

### Writing data
On destination chain (ex : Polygon), call data feed contract's `write(variableKey, data)`.

It will generate a new (one-time) slot under, and return it (+ fire an event).

### Reading data
On RaptorChain, call datafeed precompile's `getSlotData(chainid, slotowner, slotkey)`, where :
- chainid is the source chain
- slotowner is the address that wrote data
- slotkey is the one-time slot key that was fired while writing

## Datafeed addresses
### RaptorChain

### Other chains
- Polygon : `0x47C0D110eEB1357225B707E0515B17Ab0EB1CaF6`