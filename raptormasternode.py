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
        # self.stakingContract = self.chain.eth.contract(address=self.masterContract.functions.staking().call(), abi=StakingContractABI)
        self.custodyContract = self.chain.eth.contract(address=self.masterContract.functions.custody().call(), abi=CustodyContractABI)
        # self.beaconChainContract = self.chain.eth.contract(address=self.masterContract.functions.beaconchain().call(), abi=BeaconChainContractABI)
        
        
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
        self.bsc = BSCInterface("https://data-seed-prebsc-1-s1.binance.org:8545/", "0x723b074d5f653CbFCe78752DEC34301a3EA8326F", "0xC64518Fb9D74fabA4A748EA1Db1BdDA71271Dc21")
    
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

# key used during tests : 08ee5b2dd065b558af2a27df9989c6e4d01de25c194b83c449807e661c3ea2e2
# this key leads to address 0xD6dCdcFEde242Ed16dB7Cb97113025d9B6606560


nodeaddr = "http://localhost:6969/"
privkey = "08ee5b2dd065b558af2a27df9989c6e4d01de25c194b83c449807e661c3ea2e2"

producer = RaptorBlockProducer(nodeaddr, privkey)
# producer.pushBlockOnBSC({"miningData": {"miner": "0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846", "nonce": 0, "difficulty": 1, "miningTarget": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", "proof": "0x8b25b3052cb1d93f487d79771266fb330b4f52690bb1d09c26be0d247f272fa7"}, "height": 1, "parent": "0x7d9e1f415e0084675c211687b1c8dfaee67e53128e325b5fdda9c98d7288aaeb", "messages": "000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", "timestamp": 1645475025, "son": "0x0000000000000000000000000000000000000000000000000000000000000000", "signature": {"v": 28, "r": 79009779851901873211831854445404623019765375818202350246342002756271780528694, "s": 52695979310865140892079600528745975379835716148072056739716945000819311632034, "sig": "0xaeadf35de94d451ed85e37e02ea38eec1cff3811ba96ee86e13be45dc3ba02367480de09c37a08f1b42d840d90e9b73c9d9eb0d6b5a760eb27efdf184f15dea21c"}})
producer.blockProductionLoop()
