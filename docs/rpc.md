# RaptorChain RPC
RPC is the way for other softwares to query your node by sending HTTP requests.
RaptorChain node listens on port 5000. Thus, your local node can be queried on `http://localhost:5000/<path>`
Official public RPC node runs over HTTPS (forwarded to port 443). You can query it on `https://rpc.raptorchain.io/<path>`

# Return format
Node returns data in JSON format.

### Success response
```json
	{
		"success": true,
		"result": "RESULT_DEPENDS_ON_QUERY"
	}
```

### Error response
```
	{
		"success": false,
		"message": "AN ERROR MESSAGE"
	}
```

# Paths

## General queries

These are general queries. They come under `/`.

### GET `/` : Node homepage
Shows little greeting message
Example query : `https://rpc.raptorchain.io/`

### GET `/stats` : Node statistics
Shows statistics about node such as total number of transactions, chain length, number of RPTR holders and much more !

Example query : `https://rpc.raptorchain.io/stats`

### POST `/web3`
Allows to connect web3-compatible wallets (such as metamask) to RaptorChain.
You can add RaptorChain to metamask with RPC `https://rpc.raptorchain.io/web3`

It also allows to interact with RaptorChain from web3 libraries (such as `web3.py` and `web3.js`) !

## Transaction retrieving queries
The following paths are used to query raw transactions from node.

These paths ALWAYS start by `/get`

### GET `/get/transactions` : get all transactions - WILL BECOME DEPRECATED
Allows to get all transactions stored in the node. Due to the increasing volume, it WILL become deprecated in a further upgrade.

### GET `/get/transactions/<txids>`
Allows to query multiple transactions by txids (comma-separated without spaces).

Example query : `https://rpc.raptorchain.io/get/transactions/0xfd6a0eae80027f47e5ee302de62e558ad415f4e679796dd771f7ca80bf337afd,0xd9e7ae43b045ba8380f4942bc6891578682b48565bcf7f5b5327de101865fa9d`

## Account-related queries
These queries allow to query informations about RaptorChain accounts/addresses, plus some additional data from blockchain state.
Address format is the same as Ethereum's one (to ensure EVM compatibility).


### GET `/accounts/accountInfo/<address>` : get informations about an account
Allows to get informations about a specific RaptorChain address.
Allows to retrieve its balance, nonce (ethereum-like) and transaction history.

Example query : `https://rpc.raptorchain.io/accounts/accountInfo/0x3f119Cef08480751c47a6f59Af1AD2f90b319d44`

### GET `/accounts/sent/<address>` : get transactions sent by an address
Allows to get transactions sent by an address (mainly used for debug purposes).

Example query : `https://rpc.raptorchain.io/accounts/sent/0x3f119Cef08480751c47a6f59Af1AD2f90b319d44`

### GET `/accounts/accountBalance/<address>` : get balance of an account
Allows to get ONLY balance of an account (accountInfo is pretty heavy).

Example query : `https://rpc.raptorchain.io/accounts/accountBalance/0x3f119Cef08480751c47a6f59Af1AD2f90b319d44`

### GET `/account/tempcode/<address>` : get temporary code of an account
Debug query allowing to get `tempcode` variable of an account.
Basically, RaptorChain accounts have 2 code variables (`code` and `tempcode`), where `code` is permanent (written after successful transaction execution) and `tempcode` is temporary (written regardless success, allowing to have same behavior on `eth_call`)

### GET `/accounts/txChilds/{txid}` : get execution childs of a tx
Allows to get childs of a transaction.

Due to RaptorChain's nature (semi-asynchronous), tx parents/childs are part of its security model (to ensure a proper execution order).

Basically, a transaction can ONLY execute if its parent (previous transaction involving sender account) is previous transaction, protecting network against re-entrancy.

Example query : `https://rpc.raptorchain.io/accounts/txChilds/0xfd6a0eae80027f47e5ee302de62e558ad415f4e679796dd771f7ca80bf337afd`

## Transaction sending queries
Queries to send transactions, located under `/send`

### GET `/send/rawtransaction/?tx=<comma-separated txs>` : legacy send transaction (DEPRECATED)
Send hex encoded (json string to hex) raw (signed) transaction to a node !

Example query : `https://rpc.raptorchain.io/send/rawtransaction/?tx=YOUR_TRANSACTION_HERE`

### POST `/send/postrawtransaction/` : same but POST and up to date
Send your transactions as post data in the following format :
```
	{
		"txs": [tx1, tx2...] // list of transactions as string (NOT HEX)
	}
```

Example query : post `{"txs": [yourTx]}` to `https://rpc.raptorchain.io/send/postrawtransaction/`

### GET `/send/buildtransaction/` : remotely build and sign transaction - DEPRECATED
Send params (private key, amount, sender, recipient) and sign transaction.

WARNING : INVOLVE SENDING YOUR PRIVATE KEY TO THE NODE

RISK OF LOSS OF FUNDS IN CASE OF ROGUE REMOTE NODE OR HACKED NODE

## BeaconChain-related queries
Queries related to BeaconChain (the "backbone" of the network), under `/chain`

BeaconChain fills the following roles
- cross-chain message routing (message are passed through beacon blocks)
- data ordering (transactions use last beacon block as `epoch` param)
- synchronization (nodes sync transactions by beacon block)

### GET `/chain/block/<height>` : get beacon block by height
Get a beacon block by height.

Example query : `https://rpc.raptorchain.io/chain/block/10`

### GET `/chain/blockByHash/<hash>` : get beacon block by hash
Get a beacon block by hash.

Example query : `https://rpc.raptorchain.io/chain/blockByHash/0x1ab6dfa74e01df8f73208645578bfa5accab5fabb7c632373a158ae36f6ee20e`

### GET `/chain/getlastblock` : get last beacon block
Allows to get last beacon block.

Example query : `https://rpc.raptorchain.io/chain/getlastblock`

### GET `/chain/miningInfo` : get mining infos - MIGHT BECOME DEPRECATED
Gives informations about mining (difficulty, miningTarget and last block hash)

Fun fact : RaptorChain was considered to be a PoW chain, and this endpoint was added to help miners.
As RaptorChain uses a PoS-like consensus (masternodes, to be exact), it's now useless (but legacy)

Example query : `https://rpc.raptorchain.io/chain/miningInfo`

### GET `/chain/length` : beacon chain length
Returns length of BeaconChain.

Example query : `https://rpc.raptorchain.io/chain/length`

### GET `/chain/mempool` : get pending cross-chain messages
Pending cross-chain messages land here before getting included in a beacon block.

This endpoint allows to retrieve them.

Example query : `https://rpc.raptorchain.io/chain/mempool`

## Validators-related queries
Queries to get informations about validators (that produce blocks on beacon chains).
As they're part of beacon chain, they're under `/chain/validators`

### GET `/chain/validators` : get validator list
Allows to get current list of validators.

Example query : `https://rpc.raptorchain.io/chain/validators`

### GET `/chain/validators/<valoper>` : search a specific validator
Allows to search a specific validator by operator address (the address that submits blocks).

Example query : `https://rpc.raptorchain.io/chain/validators/0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846`

### GET `/chain/validators/whoseturn` : search current validator's turn to produce a block
RaptorChain uses a kind of round system (timestamp round).

Basically, each validator has a turn. Current validator index is picked by `(currentTime // 10minutes)%numberOfValidators`.
Then it picks the validator at this index.
That avoids getting multiple validators to submit a block at the same time (which would cause a lot of mess).

## Cross-Chain stuff
As cross-chain is embedded in BeaconChain, it's located under `/chain/crosschain`

### GET `/chain/crosschain` : list of supported chains
Returns list of supported chains, with their interface contracts (needs some code on destination chain) and used RPC (the one currently used by client to pull data).

Example query : `https://rpc.raptorchain.io/chain/crosschain`

### GET `/chain/crosschain/<chainid>` : get infos about a supported chain
Returns infos about a specific chain (its interface contract address + its RPC)

Example query : `https://rpc.raptorchain.io/chain/crosschain/137`

## Peer-related queries
Everything related to peers (aka the base of p2p)

### GET `/net/getPeers`
Allows to get node's known peers (both online and offline)

Example query : `https://rpc.raptorchain.io/net/getPeers`

### GET `/net/getOnlinePeers`
Allows to get node's known ONLINE peers

Example query : `https://rpc.raptorchain.io/net/getOnlinePeers`