# RaptorChain
A chain for RPTR (Raptor Token), but still under development !!!



## State of development
### What works ?
- Transfers (raptorchain address to another raptorchain address)
- Single-asset bridge (transfer RPTR between raptorchain to bsc)

### What's under development ?
- Reducing fee on withdrawal
	Basically, raptorchain-to-bsc communications works by operating an instance of raptorchain's beacon chain (which contains cross-chain data and is getting used as time anchor).
	Thus, broadcasting one block per 10 minutes is very expensive !
- Multi-asset bridge (transfer any bep20 between raptorchain and bsc)
- Consensus update
	Basically, I've added a new param `stateRoot` to beacon blocks.
	Since state root is hash of system state (account balances, masternodes...), it allows verifying a snapshot by comparing with hash in block (aka not fake-able)


## Wanna try it ?
### Testnet/devnet address
Node ip : `https://rptr-testnet-1.dynamic-dns.net/web3` (note it's http and not https, else it won't work)

chainID : `69420`

ticker : `tRPTR`


### Getting some test tokens
Will add a testnet faucet soon.

But if you wanna try network right now, feel free to ask for some test tokens (it isn't real RPTR) at [@ygboucherk on telegram](https://t.me/ygboucherk) or `yanis#3059` on discord


### Questions
If you have any question regarding raptorchain, please raise an issue (so it helps whole community as github issues are public) :D
