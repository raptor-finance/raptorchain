from web3 import Web3
from web3.auto import w3

class BSCInterface(object):
    def __init__(self, rpc, chainId, beaconInstance):
        self.token = tokenAddress
        BeaconChainContractABI = """[{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_genesisBeacon","type": "tuple"},{"internalType": "contract StakeManager","name": "_stakingContract","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "beaconHash","outputs": [{"internalType": "bytes32","name": "beaconRoot","type": "bytes32"}],"stateMutability": "pure","type": "function"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "beacons","outputs": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "chainLength","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "address","name": "validator","type": "address"}],"name": "disableValidator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "validator","type": "address"}],"name": "enableValidator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "uint256","name": "blockNumber","type": "uint256"}],"name": "getValidatorsAtBlock","outputs": [{"internalType": "address[]","name": "","type": "address[]"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "isBeaconValid","outputs": [{"internalType": "bool","name": "valid","type": "bool"},{"internalType": "string","name": "reason","type": "string"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "blockNumber","type": "uint256"},{"internalType": "address","name": "valoper","type": "address"}],"name": "isValidatorAtBlock","outputs": [{"internalType": "bool","name": "","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "pushBeacon","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [],"name": "stakingContract","outputs": [{"internalType": "contract StakeManager","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
        
        
        self.rpcurl = rpc
        self.chainID = chainId
        
        if (rpc.split(":")[0]) in ["ws", "wss"]:
            self.chain = Web3(Web3.WebsocketProvider(rpc))
        elif (rpc.split(":")[0]) in ["http", "https"]:
            self.chain = Web3(Web3.HTTPProvider(rpc))
        self.beaconInstance = self.chain.eth.contract(address=Web3.toChecksumAddress(beaconInstance), abi=BeaconChainContractABI)
        
        
    def chainLength(self):
        return self.beaconInstance.functions.chainLength().call()


class BSCPusher(object):
    def __init__(self, node, privkey, bscInterface):
        self.bsc = bscInterface
        self.node = node
        self.acct = w3.eth.account.from_key(privkey)
        print(f"Relayer BSC address : {self.acct.address}")
        
    def pushBlockOnBSC(self, block):
        # msgsList = list(eth_abi.decode_abi(["bytes[]"], bytes.fromhex(block["messages"]))[0])
        # msgsList = eth_abi.decode_abi(["bytes32[]"], bytes.fromhex(block["messages"]))
        # print(msgsList)
        # data = (self.acct.address, int(0), msgsList, 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), int(block["timestamp"]), bytes.fromhex(block["parent"].replace("0x", "")), bytes.fromhex(block["miningData"]["proof"].replace("0x", "")), int(block["height"]), bytes.fromhex(block["son"].replace("0x", "")), int(block["signature"]["v"]), bytes.fromhex(hex(block["signature"]["r"])[2:]), bytes.fromhex(hex(block["signature"]["s"])[2:]))
        data = self.blockStruct(block)
        
        _data = []
        for x in list(data):
            if type(x) == bytes:
                _data.append(f"0x{x.hex()}")
            elif type(x) == int:
                _data.append(str(x))
            else:
                _data.append(x)
        print(_data)

        tx = self.bsc.beaconInstance.functions.pushBeacon(data).buildTransaction({'nonce': self.bsc.chain.eth.get_transaction_count(self.acct.address),'chainId': self.bsc.chainID, 'gasPrice': int(11*(10**9)), "gas": 1000000, 'from':self.acct.address})
        # tx = self.bsc.stakingContract.functions.sendL2Block(self.acct.address, int(0), eth_abi.decode_abi(["bytes32[]"], bytes.fromhex(block["messages"])), 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), int(block["timestamp"]), bytes.fromhex(block["parent"].replace("0x", "")), bytes.fromhex(block["miningData"]["proof"].replace("0x", "")), int(block["height"]), bytes.fromhex(block["son"].replace("0x", "")), int(block["signature"]["v"]), bytes.fromhex(hex(block["signature"]["r"])[2:]), bytes.fromhex(hex(block["signature"]["s"])[2:])).buildTransaction({'nonce': self.bsc.chain.eth.get_transaction_count(self.acct.address),'chainId': self.bsc.chainID, 'gasPrice': 10, 'from':self.acct.address})
        signedtx = self.acct.signTransaction(tx)
        self.bsc.chain.eth.send_raw_transaction(signedtx.rawTransaction)
        txid = w3.toHex(w3.keccak(signedtx.rawTransaction))
        print(txid)
        receipt = self.bsc.chain.eth.waitForTransactionReceipt(txid)
        print(receipt)
        return receipt
    
    def pushBlocks(self):
        for i in range(int(self.bsc.chainLength()), int(int(requests.get(f"{self.node}/chain/length").json().get("result"))-1)):
            _block = requests.get(f"{self.node}/chain/block/{i}").json().get("result")
            self.pushBlockOnBSC(_block)

relayer = BSCPusher("http://localhost:2022/", BSCInterface("https://data-seed-prebsc-1-s1.binance.org:8545/", 97, None)) # Beacon instance to deploy