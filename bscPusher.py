from web3 import Web3
import helpers.abis as abis
from web3.auto import w3
from eth_account import Account
import time, requests, eth_abi, sys

class Chain(object):
    def __init__(self, chainid, rpc, gasPrice, cntAddress, eip1559=False, tip=0):
        self.chainid = chainid
        self.rpc = rpc
        self.gasPrice = int(gasPrice * (10**9))
        self.cntAddress = cntAddress
        self.eip1559 = eip1559
        self.tip = tip
        

chains = {
    "bsc" : Chain(56, "https://bscrpc.com/", 5, "0x4444F4a84d5160659E5b4D12fC2d6bC4F82B9747"),
    "polygon" : Chain(137, "https://polygon-rpc.com/", 200, "0xA479C9790C18392fDf5069a81e2e469d9bd598aB", True, 20),
    "fantom": Chain(250, "https://rpc.ftm.tools/", 120, "0x2f6bF313B0a8C30ce50D8cA3B1Dcb65EBaf318d6"),
    "ethereum": Chain(1, "https://eth.llamarpc.com/", 23, "0xDb18De2bec4DDF3b12b01193aE9D0a35141DE159", True, 0)
}

class BSCInterface(object):
    def __init__(self, params):
        BeaconChainContractABI = abis.ABI_BEACONCHAIN_MIDDLEWARE
        
        rpc = params.rpc
        self.gasPrice = params.gasPrice
        self.rpcurl = rpc
        self.chainID = params.chainid
        self.eip1559 = params.eip1559
        
        self.params = params
        
        if (rpc.split(":")[0]) in ["ws", "wss"]:
            self.chain = Web3(Web3.WebsocketProvider(rpc))
        elif (rpc.split(":")[0]) in ["http", "https"]:
            self.chain = Web3(Web3.HTTPProvider(rpc))
        self.beaconInstance = self.chain.eth.contract(address=Web3.to_checksum_address(params.cntAddress), abi=BeaconChainContractABI)
        
        
    def buildTx(self, call, _from):
        return call.build_transaction({'nonce': self.chain.eth.get_transaction_count(_from),'chainId': self.chainID,'maxFeePerGas': self.gasPrice, "maxPriorityFeePerGas": self.params.tip, 'from':_from}) if self.eip1559 else call.build_transaction({'nonce': self.chain.eth.get_transaction_count(_from),'chainId': self.chainID,'gasPrice': self.gasPrice, 'from':_from})
        
    def chainLength(self):
        return self.beaconInstance.functions.chainLength().call()


class BSCPusher(object):
    def __init__(self, node, privkey, bscInterface):
        self.bsc = bscInterface
        self.node = node
        self.acct = Account.from_key(privkey)
        print(f"Relayer address : {self.acct.address}")

    def bytes32Padding(self, hexStr):
        _hexstr = hexStr.replace("0x", "")
        return (("0" * (64 - len(_hexstr))) + _hexstr)

    def blockStruct(self, block):
        msgsList = list(eth_abi.decode(["bytes[]"], bytes.fromhex(block["messages"]))[0])
        # msgsList = eth_abi.decode_abi(["bytes32[]"], bytes.fromhex(block["messages"]))
        _encodedParent = bytes.fromhex(block["parent"].replace("0x", ""))
        _encodedProof = bytes.fromhex(block["miningData"]["proof"].replace("0x", ""))
        _encodedSon = bytes.fromhex(block["son"].replace("0x", ""))
        _encodedSigR = bytes.fromhex(self.bytes32Padding(hex(block["signature"]["r"])[2:]))
        _encodedSigS = bytes.fromhex(self.bytes32Padding(hex(block["signature"]["s"])[2:]))
        relayerSigs = [bytes.fromhex(s.replace("0x", "")) for s in block.get("relayerSigs", [])]
        return (block["miningData"]["miner"], int(0), msgsList, 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), int(block["timestamp"]), _encodedParent, _encodedProof, int(block["height"]), _encodedSon, block["parentTxRoot"], int(block["signature"]["v"]), _encodedSigR, _encodedSigS, relayerSigs)

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
        print("Attempting to push block", data[8])

        tx = self.bsc.buildTx(self.bsc.beaconInstance.functions.pushBeacon(data), self.acct.address)
        # tx = self.bsc.stakingContract.functions.sendL2Block(self.acct.address, int(0), eth_abi.decode_abi(["bytes32[]"], bytes.fromhex(block["messages"])), 1, bytes.fromhex("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), int(block["timestamp"]), bytes.fromhex(block["parent"].replace("0x", "")), bytes.fromhex(block["miningData"]["proof"].replace("0x", "")), int(block["height"]), bytes.fromhex(block["son"].replace("0x", "")), int(block["signature"]["v"]), bytes.fromhex(hex(block["signature"]["r"])[2:]), bytes.fromhex(hex(block["signature"]["s"])[2:])).buildTransaction({'nonce': self.bsc.chain.eth.get_transaction_count(self.acct.address),'chainId': self.bsc.chainID, 'gasPrice': 10, 'from':self.acct.address})
        signedtx = self.acct.sign_transaction(tx)
        self.bsc.chain.eth.send_raw_transaction(signedtx.rawTransaction)
        txid = w3.to_hex(w3.keccak(signedtx.rawTransaction))
        print(txid)
        receipt = self.bsc.chain.eth.wait_for_transaction_receipt(txid)
        print(receipt)
        return receipt
    
    def pushBlocks(self):
        for i in range(int(self.bsc.chainLength()), int(int(requests.get(f"{self.node}/chain/length").json().get("result")))):
            _block = requests.get(f"{self.node}/chain/block/{i}").json().get("result")
            self.pushBlockOnBSC(_block)

privkey = input("Enter private key : ")
chainChoice = sys.argv[1].lower() if (len(sys.argv) > 1) else "bsc"
_params = chains.get(chainChoice, chains["bsc"])
relayer = BSCPusher("https://rpc.raptorchain.io/", privkey, BSCInterface(_params)) # Beacon instance to deploy

while True:
    try:
        relayer.pushBlocks()
    except Exception as e:
        print(e)
    time.sleep(15)