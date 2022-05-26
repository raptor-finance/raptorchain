from web3.auto import w3
import eth_abi, requests, time, json
from web3 import Web3
from eth_account.messages import encode_defunct

class BSCInterface(object):
    def __init__(self, rpc, MasterContractAddress, tokenAddress):
        self.token = tokenAddress
        MasterContractABI = """[{"inputs": [{"internalType": "address","name": "stakingToken","type": "address"},{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_genesisBeacon","type": "tuple"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [],"name": "beaconchain","outputs": [{"internalType": "contract BeaconChainHandler","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "custody","outputs": [{"internalType": "contract CustodyManager","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "staking","outputs": [{"internalType": "contract StakeManager","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
        StakingContractABI = """[{"inputs": [{"internalType": "address","name": "_stakingToken","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [],"name": "beaconChain","outputs": [{"internalType": "contract BeaconChainHandler","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "claimMNRewards","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "createMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "destroyMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "disableMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "enableMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "","type": "address"}],"name": "masternodes","outputs": [{"internalType": "address","name": "owner","type": "address"},{"internalType": "address","name": "operator","type": "address"},{"internalType": "uint256","name": "collateral","type": "uint256"},{"internalType": "uint256","name": "rewards","type": "uint256"},{"internalType": "bool","name": "operating","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_block","type": "tuple"}],"name": "sendL2Block","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "contract BeaconChainHandler","name": "_handler","type": "address"}],"name": "setBeaconHandler","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [],"name": "stakingToken","outputs": [{"internalType": "contract ERC20Interface","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
        CustodyContractABI = """[{"inputs": [{"internalType": "contract StakeManager","name": "_stakingManager","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"anonymous": false,"inputs": [{"indexed": true,"internalType": "address","name": "depositor","type": "address"},{"indexed": true,"internalType": "address","name": "token","type": "address"},{"indexed": false,"internalType": "uint256","name": "amount","type": "uint256"},{"indexed": false,"internalType": "uint256","name": "nonce","type": "uint256"},{"indexed": false,"internalType": "bytes32","name": "hash","type": "bytes32"}],"name": "Deposited","type": "event"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "__deposits","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "__withdrawals","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes32","name": "","type": "bytes32"}],"name": "_deposits","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes32","name": "","type": "bytes32"}],"name": "_withdrawals","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes","name": "_data","type": "bytes"}],"name": "bridgeFallBack","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "token","type": "address"},{"internalType": "uint256","name": "amount","type": "uint256"}],"name": "deposit","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "bytes32","name": "_hash","type": "bytes32"}],"name": "deposits","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"internalType": "struct CustodyManager.Deposit","name": "","type": "tuple"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "_index","type": "uint256"}],"name": "deposits","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"internalType": "struct CustodyManager.Deposit","name": "","type": "tuple"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "depositsLength","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "stakingManager","outputs": [{"internalType": "contract StakeManager","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "totalDeposited","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "transferNonce","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "_index","type": "uint256"}],"name": "withdrawals","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"internalType": "struct CustodyManager.Withdrawal","name": "","type": "tuple"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes32","name": "_hash","type": "bytes32"}],"name": "withdrawals","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"internalType": "struct CustodyManager.Withdrawal","name": "","type": "tuple"}],"stateMutability": "view","type": "function"}]"""
        BeaconChainContractABI = """[{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_genesisBeacon","type": "tuple"},{"internalType": "contract StakeManager","name": "_stakingContract","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "beaconHash","outputs": [{"internalType": "bytes32","name": "beaconRoot","type": "bytes32"}],"stateMutability": "pure","type": "function"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "beacons","outputs": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "chainLength","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "address","name": "validator","type": "address"}],"name": "disableValidator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "validator","type": "address"}],"name": "enableValidator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "uint256","name": "blockNumber","type": "uint256"}],"name": "getValidatorsAtBlock","outputs": [{"internalType": "address[]","name": "","type": "address[]"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "isBeaconValid","outputs": [{"internalType": "bool","name": "valid","type": "bool"},{"internalType": "string","name": "reason","type": "string"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "blockNumber","type": "uint256"},{"internalType": "address","name": "valoper","type": "address"}],"name": "isValidatorAtBlock","outputs": [{"internalType": "bool","name": "","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "pushBeacon","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [],"name": "stakingContract","outputs": [{"internalType": "contract StakeManager","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
        
        
        self.rpcurl = rpc
        self.chainID = 97
        
        if (rpc.split(":")[0]) in ["ws", "wss"]:
            self.chain = Web3(Web3.WebsocketProvider(rpc))
        elif (rpc.split(":")[0]) in ["http", "https"]:
            self.chain = Web3(Web3.HTTPProvider(rpc))
        self.masterContract = self.chain.eth.contract(address=Web3.toChecksumAddress(MasterContractAddress), abi=MasterContractABI)
        # self.stakingContract = self.chain.eth.contract(address=self.masterContract.functions.staking().call(), abi=StakingContractABI)
        self.custodyContract = self.chain.eth.contract(address=self.masterContract.functions.custody().call(), abi=CustodyContractABI)
        # self.beaconChainContract = self.chain.eth.contract(address=self.masterContract.functions.beaconchain().call(), abi=BeaconChainContractABI)
        
        
    def getDepositDetails(self, _hash):
        returnValue = {}
        (returnValue["amount"], returnValue["depositor"], returnValue["nonce"], returnValue["token"], returnValue["hash"]) = self.custodyContract.functions.deposits(_hash).call()
        if (w3.toChecksumAddress(self.token) != w3.toChecksumAddress(returnValue["token"])):
            returnValue["amount"] = 0
        return returnValue

    def chainLength(self):
        print(self.beaconChainContract.address)
        return self.beaconChainContract.functions.chainLength().call()

class RaptorBlockProducer(object):
    def __init__(self, nodeip, privkey):
        self.node = nodeip
        self.acct = w3.eth.account.from_key(privkey)
        self.bsc = BSCInterface("https://data-seed-prebsc-1-s1.binance.org:8545/", "0x723b074d5f653CbFCe78752DEC34301a3EA8326F", "0xC64518Fb9D74fabA4A748EA1Db1BdDA71271Dc21")
        self.defaultMessage = eth_abi.encode_abi(["address", "uint256", "bytes"], ["0x0000000000000000000000000000000000000000", 0, b""])
    
    def pullAvailableMessages(self):
        hexmessages = requests.get(f"{self.node}/chain/mempool").json().get("result")
        bytesmessages = []
        for hexmsg in hexmessages:
            bytesmessages.append(bytes.fromhex(hexmsg.replace("0x", "")))
        return bytesmessages
    
    
    def blockHash(self, block):
        messagesHash = w3.keccak(bytes.fromhex(block["messages"])).hex()
        bRoot = w3.soliditySha3(["bytes32", "uint256", "bytes32", "bytes32", "address"], [block["parent"], int(block["timestamp"]), messagesHash, block["parentTxRoot"], self.acct.address]).hex() # parent PoW hash (bytes32), beacon's timestamp (uint256), hash of messages (bytes32), beacon miner (address)
        return w3.soliditySha3(["bytes32", "uint256"], [bRoot, int(0)]).hex()
    
    def buildBlock(self):
        blockHeight = requests.get(f"{self.node}/chain/length").json().get("result")
        lastBlock = requests.get(f"{self.node}/chain/getlastblock").json().get("result")
        print(lastBlock)
        lastBlockHash = lastBlock.get("miningData").get("proof")
        parentTxRoot = lastBlock.get("txsRoot")
        pulledMessages = self.pullAvailableMessages()
        if (len(pulledMessages) == 0):
            pulledMessages = [self.defaultMessage]
        
        abiencodedmessages = eth_abi.encode_abi(["bytes[]"], [pulledMessages])
        
        blockData = {"parentTxRoot": parentTxRoot, "miningData" : {"miner": self.acct.address,"nonce": 0,"difficulty": 1,"miningTarget": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff","proof": None}, "height": blockHeight,"parent": lastBlockHash,"messages": abiencodedmessages.hex(), "timestamp": int(time.time()), "son": "0000000000000000000000000000000000000000000000000000000000000000", "signature": {"v": None, "r": None, "s": None, "sig": None}}
        blockData["miningData"]["proof"] = self.blockHash(blockData)
        print(blockData["miningData"]["proof"])
        _sig = self.acct.signHash(blockData["miningData"]["proof"])
        blockData["signature"]["v"] = _sig.v
        blockData["signature"]["r"] = _sig.r
        blockData["signature"]["s"] = _sig.s
        blockData["signature"]["sig"] = _sig.signature.hex()
        return blockData
        
    def submitBlock(self, block):
        acctTxs = requests.get(f"{self.node}/accounts/accountInfo/{self.acct.address}").json().get("result").get("transactions")
        lastTx = acctTxs[len(acctTxs)-1]
        epoch = block["parent"]
        txdata = json.dumps({"from": "0x0000000000000000000000000000000000000000", "to": "0x0000000000000000000000000000000000000000", "tokens": 0, "parent": lastTx, "epoch": epoch, "blockData": block, "indexToCheck": self.bsc.custodyContract.functions.depositsLength().call(), "type": 1})
        tx = json.dumps({"data": txdata, "sig": self.acct.sign_message(encode_defunct(text=txdata)).signature.hex(), "hash": w3.solidityKeccak(["string"], [txdata]).hex()}).encode().hex()
        feedback = requests.get(f"{self.node}/send/rawtransaction/?tx={tx}").json()
        print(feedback)
        return feedback
    
    
    
    def blockStruct(self, block):
        msgsList = list(eth_abi.decode_abi(["bytes[]"], bytes.fromhex(block["messages"]))[0])
        # msgsList = eth_abi.decode_abi(["bytes32[]"], bytes.fromhex(block["messages"]))
        _encodedParent = bytes.fromhex(block["parent"].replace("0x", ""))
        _encodedProof = bytes.fromhex(block["miningData"]["proof"].replace("0x", ""))
        _encodedSon = bytes.fromhex(block["son"].replace("0x", ""))
        _encodedSigR = bytes.fromhex(hex(block["signature"]["r"])[2:])
        print(hex(block["signature"]["s"]))
        _encodedSigS = bytes.fromhex(hex(block["signature"]["s"])[2:])
        
        return (self.acct.address, int(0), msgsList, 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), int(block["timestamp"]), _encodedParent, _encodedProof, int(block["height"]), _encodedSon, int(block["signature"]["v"]), _encodedSigR, _encodedSigS)
    
    def produceNewBlock(self):
        _block = self.buildBlock()
        _submitFeedBack = self.submitBlock(_block)
        # try:
            # # _bscPushFeedback = self.pushBlockOnBSC(_block)
        # except Exception as e:
            # print(e)
        
    def blockProductionLoop(self):
        while True:
            try:
                self.produceNewBlock()
                time.sleep(60)
            except Exception as e:
                print(f"Exception caught : {e}")

# key used during tests : 47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad
# this key leads to address 0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846


nodeaddr = "http://localhost:6969/"
privkey = "47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad"

producer = RaptorBlockProducer(nodeaddr, privkey)
# producer.pushBlockOnBSC({"miningData": {"miner": "0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846", "nonce": 0, "difficulty": 1, "miningTarget": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", "proof": "0x8b25b3052cb1d93f487d79771266fb330b4f52690bb1d09c26be0d247f272fa7"}, "height": 1, "parent": "0x7d9e1f415e0084675c211687b1c8dfaee67e53128e325b5fdda9c98d7288aaeb", "messages": "000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", "timestamp": 1645475025, "son": "0x0000000000000000000000000000000000000000000000000000000000000000", "signature": {"v": 28, "r": 79009779851901873211831854445404623019765375818202350246342002756271780528694, "s": 52695979310865140892079600528745975379835716148072056739716945000819311632034, "sig": "0xaeadf35de94d451ed85e37e02ea38eec1cff3811ba96ee86e13be45dc3ba02367480de09c37a08f1b42d840d90e9b73c9d9eb0d6b5a760eb27efdf184f15dea21c"}})
producer.blockProductionLoop()
