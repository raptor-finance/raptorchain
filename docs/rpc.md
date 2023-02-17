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

## Transaction-related queries
The following paths are used to query raw transactions from node.

These paths ALWAYS start by `/get`

### GET `/get/transactions` : get all transactions - WILL BECOME DEPRECATED
Allows to get all transactions stored in the node. Due to the increasing volume, it WILL become deprecated in a further upgrade.

### GET `/get/transactions/<txids>`
Allows to query multiple transactions by txids (comma-separated without spaces).

Example query : `https://rpc.raptorchain.io/get/transactions/0xfd6a0eae80027f47e5ee302de62e558ad415f4e679796dd771f7ca80bf337afd,0xd9e7ae43b045ba8380f4942bc6891578682b48565bcf7f5b5327de101865fa9d`

## Account-related queries
These queries allow to query informations about RaptorChain accounts/addresses.
Address format is the same as Ethereum's one (to ensure EVM compatibility).

### GET `/accounts/accountInfo/<address>`
Allows to get informations about a specific RaptorChain address.
Allows to retrieve its balance, nonce (ethereum-like) and transaction history.

Example query : `https://rpc.raptorchain.io/accounts/accountInfo/0x3f119Cef08480751c47a6f59Af1AD2f90b319d44`

