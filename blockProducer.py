from web3.auto import w3
import eth_abi, requests, time, json
from web3 import Web3
from eth_account import Account
from helpers.utils import lastOf, signTxData, assembleBlockData, signBlockData, defaultMessages, beaconBlockStruct
import helpers.abis as abis

class BSCInterface(object):
    def __init__(self, rpc, MasterContractAddress, tokenAddress):
        self.token = tokenAddress
        MasterContractABI = abis.ABI_MASTER_CLIENT
        StakingContractABI = abis.ABI_STAKING
        CustodyContractABI = abis.ABI_CUSTODY_STAKING_MANAGER
        BeaconChainContractABI = abis.ABI_BEACONCHAIN_LEGACY
        
        
        self.rpcurl = rpc
        self.chainID = 97
        
        if (rpc.split(":")[0]) in ["ws", "wss"]:
            self.chain = Web3(Web3.WebsocketProvider(rpc))
        elif (rpc.split(":")[0]) in ["http", "https"]:
            self.chain = Web3(Web3.HTTPProvider(rpc))
        self.masterContract = self.chain.eth.contract(address=Web3.to_checksum_address(MasterContractAddress), abi=MasterContractABI)
        self.stakingContract = self.chain.eth.contract(address=self.masterContract.functions.staking().call(), abi=StakingContractABI)
        self.custodyContract = self.chain.eth.contract(address=self.masterContract.functions.custody().call(), abi=CustodyContractABI)
        self.beaconChainContract = self.chain.eth.contract(address=self.masterContract.functions.beaconchain().call(), abi=BeaconChainContractABI)
        
        
    def getDepositDetails(self, _hash):
        returnValue = {}
        (returnValue["amount"], returnValue["depositor"], returnValue["nonce"], returnValue["token"], returnValue["hash"]) = self.custodyContract.functions.deposits(_hash).call()
        if (w3.to_checksum_address(self.token) != w3.to_checksum_address(returnValue["token"])):
            returnValue["amount"] = 0
        return returnValue

    def currentDepositsIndex(self):
        # live on-chain read - MUST NOT cache (drives indexToCheck semantics)
        return self.custodyContract.functions.depositsLength().call()

    def chainLength(self):
        print(self.beaconChainContract.address)
        return self.beaconChainContract.functions.chainLength().call()

class RaptorBlockProducer(object):
    def __init__(self, nodeip, privkey):
        self.node = nodeip
        self.acct = Account.from_key(privkey)
        self.bsc = BSCInterface("https://data-seed-prebsc-1-s1.binance.org:8545/", "0x62bba42220be7acf52bb923a0bdc098ff4db4a36", "0xC64518Fb9D74fabA4A748EA1Db1BdDA71271Dc21")
    
    def pullAvailableMessages(self):
        hexmessages = requests.get(f"{self.node}/chain/mempool").json().get("result")
        bytesmessages = []
        for hexmsg in hexmessages:
            bytesmessages.append(bytes.fromhex(hexmsg.replace("0x", "")))
        return bytesmessages
    
    
    def buildBlock(self):
        blockHeight = requests.get(f"{self.node}/chain/length").json().get("result")
        lastBlock = requests.get(f"{self.node}/chain/getlastblock").json().get("result")
        lastBlockHash = lastBlock.get("miningData").get("proof")
        parentTxRoot = lastBlock.get("txsRoot")
        pulledMessages = self.pullAvailableMessages()
        if (len(pulledMessages) == 0):
            pulledMessages = defaultMessages()
        
        abiencodedmessages = eth_abi.encode(["bytes[]"], [pulledMessages])
        
        blockData = assembleBlockData(self.acct.address, blockHeight, lastBlockHash, parentTxRoot, abiencodedmessages.hex())
        return signBlockData(self.acct, blockData)
        
    def submitBlock(self, block):
        acctTxs = requests.get(f"{self.node}/accounts/accountInfo/{self.acct.address}").json().get("result").get("transactions")
        lastTx = lastOf(acctTxs)
        epoch = block["parent"]
        txdata = json.dumps({"from": "0x0000000000000000000000000000000000000000", "to": "0x0000000000000000000000000000000000000000", "tokens": 0, "parent": lastTx, "epoch": epoch, "blockData": block, "indexToCheck": self.bsc.currentDepositsIndex(), "type": 1})
        tx = json.dumps(signTxData(self.acct, txdata)).encode().hex()
        feedback = requests.get(f"{self.node}/send/rawtransaction/?tx={tx}").json()
        print(feedback)
        return feedback
    
    
    
    def blockStruct(self, block):
        return beaconBlockStruct(self.acct.address, block)

    def pushMissingBlocksToBSC(self):
        for i in range(int(self.bsc.chainLength()), int(int(requests.get(f"{self.node}/chain/length").json().get("result"))-1)):
            _block = requests.get(f"{self.node}/chain/block/{i}").json().get("result")
            self.pushBlockOnBSC(_block)

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

        tx = self.bsc.stakingContract.functions.sendL2Block(data).build_transaction({'nonce': self.bsc.chain.eth.get_transaction_count(self.acct.address),'chainId': self.bsc.chainID, 'gasPrice': int(11*(10**9)), "gas": 1000000, 'from':self.acct.address})
        # tx = self.bsc.stakingContract.functions.sendL2Block(self.acct.address, int(0), eth_abi.decode_abi(["bytes32[]"], bytes.fromhex(block["messages"])), 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), int(block["timestamp"]), bytes.fromhex(block["parent"].replace("0x", "")), bytes.fromhex(block["miningData"]["proof"].replace("0x", "")), int(block["height"]), bytes.fromhex(block["son"].replace("0x", "")), int(block["signature"]["v"]), bytes.fromhex(hex(block["signature"]["r"])[2:]), bytes.fromhex(hex(block["signature"]["s"])[2:])).buildTransaction({'nonce': self.bsc.chain.eth.get_transaction_count(self.acct.address),'chainId': self.bsc.chainID, 'gasPrice': 10, 'from':self.acct.address})
        signedtx = self.acct.sign_transaction(tx)
        self.bsc.chain.eth.send_raw_transaction(signedtx.rawTransaction)
        txid = w3.to_hex(w3.keccak(signedtx.rawTransaction))
        print(txid)
        receipt = self.bsc.chain.eth.wait_for_transaction_receipt(txid)
        print(receipt)
        return receipt
    
    def produceNewBlock(self):
        _block = self.buildBlock()
        _submitFeedBack = self.submitBlock(_block)
        # try:
            # # _bscPushFeedback = self.pushBlockOnBSC(_block)
        # except Exception as e:
            # print(e)
        
    def blockProductionLoop(self):
        while True:
            self.pushMissingBlocksToBSC()
            self.produceNewBlock()
            self.pushMissingBlocksToBSC()
            time.sleep(60)

# key used during tests : 47173285a8d7341e5e972fc677286384f802f8ef42a5ec5f03bbfa254cb01fad
# this key leads to address 0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846


nodeaddr = input("Input node address here : ")
privkey = input("Input private key here : ")

producer = RaptorBlockProducer(nodeaddr, privkey)
# producer.pushBlockOnBSC({"miningData": {"miner": "0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846", "nonce": 0, "difficulty": 1, "miningTarget": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", "proof": "0x8b25b3052cb1d93f487d79771266fb330b4f52690bb1d09c26be0d247f272fa7"}, "height": 1, "parent": "0x7d9e1f415e0084675c211687b1c8dfaee67e53128e325b5fdda9c98d7288aaeb", "messages": "000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", "timestamp": 1645475025, "son": "0x0000000000000000000000000000000000000000000000000000000000000000", "signature": {"v": 28, "r": 79009779851901873211831854445404623019765375818202350246342002756271780528694, "s": 52695979310865140892079600528745975379835716148072056739716945000819311632034, "sig": "0xaeadf35de94d451ed85e37e02ea38eec1cff3811ba96ee86e13be45dc3ba02367480de09c37a08f1b42d840d90e9b73c9d9eb0d6b5a760eb27efdf184f15dea21c"}})
producer.blockProductionLoop()
