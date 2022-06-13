import requests, time, json, threading, flask, rlp, eth_abi, itertools
global config
from web3.auto import w3
from web3 import Web3
from eth_account.messages import encode_defunct
from flask_cors import CORS
from dataclasses import asdict, dataclass
from typing import Optional
from eth_utils import keccak
from rlp.sedes import Binary, big_endian_int, binary
import evmimplementation as EVM


transactions = {}
try:
    configFile = open("raptorchainconfig.json", "r")
    config = json.load(configFile)
    configFile.close()
except:
    config = {"dataBaseFile": "raptorchain-testnet-v0.4_TEST.json", "nodePrivKey": "20735cc14fd4a86a2516d12d880b3fa27f183a381c5c167f6ff009554c1edc69", "peers":["https://rpc-testnet.raptorchain.io/"], "InitTxID": "RPTRTESTNET-TRYING0.4", "netLogFile": "rptrnetlog.log"}


def isNotComment(line):
    return ((not "#" in line) and (line != "DISMISSCONFIG"))

try:
    peersFile = open("peers.txt", "r")
    _splittedLines = peersFile.read().splitlines()
    _peersFromFile = list(filter(isNotComment, _splittedLines))
    peersFile.close()
    config["peers"] = _peersFromFile if "DISMISSCONFIG" in _splittedLines else config["peers"] + _peersFromFile # dismisses config if keyword "DISMISSCONFIG"
except:
    pass # peers.txt not mandatory

try:
    ssl_context = tuple(config["ssl"])
except:
    ssl_context = None

class SignatureManager(object):
    def __init__(self):
        self.verified = 0
        self.signed = 0
    
    def signTransaction(self, private_key, transaction):
        message = encode_defunct(text=transaction["data"])
        transaction["hash"] = w3.soliditySha3(["string"], [transaction["data"]]).hex()
        _signature = w3.eth.account.sign_message(message, private_key=private_key).signature.hex()
        signer = w3.eth.account.recover_message(message, signature=_signature)
        sender = w3.toChecksumAddress(json.loads(transaction["data"])["from"])
        if (signer == sender):
            transaction["sig"] = _signature
            self.signed += 1
        return transaction
        
    def verifyTransaction(self, transaction):
        message = encode_defunct(text=transaction["data"])
        _hash = w3.soliditySha3(["string"], [transaction["data"]]).hex()
        _hashInTransaction = transaction["hash"]
        signer = w3.eth.account.recover_message(message, signature=transaction["sig"])
        sender = w3.toChecksumAddress(json.loads(transaction["data"])["from"])
        result = ((signer == sender) and (_hash == _hashInTransaction))
        self.verified += int(result)
        return result

class ETHTransactionDecoder(object):
    class Transaction(rlp.Serializable):
        fields = [
            ("nonce", big_endian_int),
            ("gas_price", big_endian_int),
            ("gas", big_endian_int),
            ("to", Binary.fixed_length(20, allow_empty=True)),
            ("value", big_endian_int),
            ("data", binary),
            ("v", big_endian_int),
            ("r", big_endian_int),
            ("s", big_endian_int),
        ]


    @dataclass
    class DecodedTx:
        hash_tx: str
        from_: str
        to: Optional[str]
        nonce: int
        gas: int
        gas_price: int
        value: int
        data: str
        chain_id: int
        r: str
        s: str
        v: int


    def decode_raw_tx(self, raw_tx: str):
        bytesTx = bytes.fromhex(raw_tx.replace("0x", ""))
        tx = rlp.decode(bytesTx, self.Transaction)
        hash_tx = w3.toHex(keccak(bytesTx))
        from_ = w3.eth.account.recover_transaction(raw_tx)
        to = w3.toChecksumAddress(tx.to) if tx.to else None
        data = w3.toHex(tx.data)
        r = hex(tx.r)
        s = hex(tx.s)
        chain_id = (tx.v - 35) // 2 if tx.v % 2 else (tx.v - 36) // 2
        return self.DecodedTx(hash_tx, from_, to, tx.nonce, tx.gas, tx.gas_price, tx.value, data, chain_id, r, s, tx.v)



class Message(object):
    def __init__(self, _from, _to, msg):
        self.sender = _from
        self.recipient = _to
        self.msg = msg

class Transaction(object):
    def __init__(self, tx):
        txData = json.loads(tx["data"])
        self.contractDeployment = False
        self.txtype = (txData.get("type") or 0)
        self.messages = []
        self.affectedAccounts = []
        self.nonce = 0
        _sig = tx.get("sig")
        self.sig = bytes.fromhex(_sig.replace("0x", "")) if _sig else b""
        if _sig:
            (self.v, self.r, self.s) = (self.sig[64], self.sig[0:32], self.sig[32:64])
        if (self.txtype == 0): # legacy transfer
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.recipient = w3.toChecksumAddress(txData.get("to"))
            self.value = max(int(txData.get("tokens")), 0)
            self.affectedAccounts = [self.sender, self.recipient]
            self.gasprice = 0
            self.gasLimit = 69000
            self.fee = self.gasprice*self.gasLimit
            try:
                self.data = bytes.fromhex(txData.get("callData", "").replace("0x", ""))
            except:
                self.data = b""
        if (self.txtype == 1): # block mining/staking tx
            self.fee = 0
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.blockData = txData.get("blockData")
            self.recipient = "0x0000000000000000000000000000000000000000"
            self.value = 0
            self.affectedAccounts = [self.sender]
            self.gasprice = 0
        elif self.txtype == 2: # metamask transaction
            decoder = ETHTransactionDecoder()
            ethDecoded = decoder.decode_raw_tx(txData.get("rawTx"))
            self.gasprice = ethDecoded.gas_price
            self.gasLimit = ethDecoded.gas
            self.fee = ethDecoded.gas_price*21000
            self.sender = ethDecoded.from_
            self.recipient = ethDecoded.to
            self.value = int(ethDecoded.value)
            self.nonce = ethDecoded.nonce
            self.ethData = ethDecoded.data
            self.ethTxid = ethDecoded.hash_tx
            self.v = ethDecoded.v
            self.r = ethDecoded.r
            self.s = ethDecoded.s
            self.data = bytes.fromhex(ethDecoded.data.replace("0x", ""))
            if not self.recipient:
                self.recipient = w3.toChecksumAddress(w3.keccak(rlp.encode([bytes.fromhex(self.sender.replace("0x", "")), int(self.nonce)]))[12:])
                self.contractDeployment = True
        elif self.txtype == 3: # deposits checking trigger
            self.fee = 0
            self.l2hash = txData["l2hash"]
            self.value = 0
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.recipient = "0x0000000000000000000000000000000000000000"
            self.affectedAccounts = [self.sender]
        elif self.txtype == 4: # MN create
            self.fee = 0
            self.value = 1000000000000000000000000
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.recipient = w3.toChecksumAddress(txData.get("to"))
            self.affectedAccounts = [self.sender, self.recipient]
        elif self.txtype == 5: # MN destroy
            self.fee = 0
            self.value = 0
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.recipient = w3.toChecksumAddress(txData.get("to"))
            self.affectedAccounts = [self.sender, self.recipient]
        elif self.txtype == 6: # system transaction
            self.fee = 0
            self.sender = "0x0000000000000000000000000000000000000000"
            self.recipient = "0x0000000000000000000000000000000000000000"
            self.value = 0
        elif self.txtype == 7: # relayer sign block
            self.fee = 0
            self.sender = txData.get("from")
            self.recipient = "0x0000000000000000000000000000000000000000"
            self.blocksig = txData.get("blocksig")
            self.value = 0
        
        self.epoch = txData.get("epoch")
        self.bio = txData.get("bio")
        self.parent = txData.get("parent")
        self.message = txData.get("message")
        self.txid = w3.soliditySha3(["string"], [tx["data"]]).hex()
        self.indexToCheck = txData.get("indexToCheck", 0)
        
        # self.PoW = ""
        # self.endTimeStamp = 0
        
    def formatAddress(self, _addr):
        if (type(_addr) == int):
            hexfmt = hex(_addr)[2:]
            return w3.toChecksumAddress("0x" + ("0" * (40-len(hexfmt))) + hexfmt)
        return w3.toChecksumAddress(_addr)
        
    def markAccountAffected(self, addr):
        _addr = self.formatAddress(addr)
        if not _addr in self.affectedAccounts:
            self.affectedAccounts.append(_addr)

    def web3Returnable(self):
        return {"hash": self.txid, "nonce": hex(self.nonce), "blockHash": self.txid, "transactionIndex": "0x0", "from": self.sender, "to": (None if self.contractDeployment else self.recipient), "value": hex(self.value), "gasPrice": hex(self.gasprice), "gas": hex(self.gasLimit), "input": self.data.hex(), "v": self.v, "r": self.r.hex(), "s": self.s.hex()}


class BeaconChain(object):
    class Masternode(object):
        def __init__(self, owner, operator):
            self.owner = w3.toChecksumAddress(owner)
            self.operator = w3.toChecksumAddress(operator)
            self.collateral = 1000000000000000000000000
            self.hash = w3.solidityKeccak(["address", "address", "uint256"], [self.owner, self.operator, int(self.collateral)])
        
        def updateHash(self):
            self.hash = w3.solidityKeccak(["address", "address", "uint256"], [self.owner, self.operator, int(self.collateral)])

        def JSONSerializable(self):
            return {"owner": self.owner, "operator": self.operator, "collateral": self.collateral, "hash": self.hash.hex()}

    class BSCInterface(object):
        class CachedToken(object):
            def __init__(self, instance, cacheValue={}):
                self.BEP20Instance = instance
                self.name = cacheValue.get("name") if cacheValue.get("name") else self.BEP20Instance.functions.name().call()
                self.symbol = cacheValue.get("symbol") if cacheValue.get("symbol") else self.BEP20Instance.functions.symbol().call()
                self.decimals = cacheValue.get("decimals") if cacheValue.get("decimals") else self.BEP20Instance.functions.decimals().call()
                self.address = self.BEP20Instance.address
                
            def JSONSerializable(self):
                return {"name": self.name, "symbol": self.symbol, "decimals": self.decimals}
    
        class CachedDeposit(object):
            class CachedDepositException(Exception):
                def __init__(self):
                    pass
                
                
            def __init__(self, depositData=None, cacheData=None):
                if (depositData and cacheData) or (not (depositData or cacheData)):
                    raise CachedDepositException("Error with inputs")
                if depositData:
                    (self.amount, self.depositor, self.nonce, self.token, self.data, self.hash) = depositData
                elif cacheData:
                    (self.amount, self.depositor, self.nonce, self.token, self.data, self.hash) = (cacheData.get("amount"), cacheData.get("depositor"), cacheData.get("nonce"), cacheData.get("token"), bytes.fromhex(cacheData.get("data").replace("0x", "")), bytes.fromhex(cacheData.get("hash").replace("0x", "")))
                
                self.legacyFormat = {"amount": self.amount, "depositor": self.depositor, "nonce": self.nonce, "token": self.token, "data": self.data, "hash": self.hash}
                
            def JSONSerializable(self):
                return {"amount": self.amount, "depositor": self.depositor, "nonce": self.nonce, "token": self.token, "data": self.data.hex(), "hash": self.hash.hex()}
    
        def __init__(self, rpc, MasterContractAddress, tokenAddress, cacheFile="BSCcache.json"):
            self.token = tokenAddress
            MasterContractABI = """[{"inputs": [{"internalType": "address","name": "stakingToken","type": "address"},{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_genesisBeacon","type": "tuple"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [],"name": "beaconchain","outputs": [{"internalType": "contract BeaconChainHandler","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "custody","outputs": [{"internalType": "contract CustodyManager","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "staking","outputs": [{"internalType": "contract StakeManager","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
            StakingContractABI = """[{"inputs": [{"internalType": "address","name": "_stakingToken","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [],"name": "beaconChain","outputs": [{"internalType": "contract BeaconChainHandler","name": "","type": "address"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "claimMNRewards","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "createMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "destroyMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "disableMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "nodeOperator","type": "address"}],"name": "enableMN","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "","type": "address"}],"name": "masternodes","outputs": [{"internalType": "address","name": "owner","type": "address"},{"internalType": "address","name": "operator","type": "address"},{"internalType": "uint256","name": "collateral","type": "uint256"},{"internalType": "uint256","name": "rewards","type": "uint256"},{"internalType": "bool","name": "operating","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_block","type": "tuple"}],"name": "sendL2Block","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "contract BeaconChainHandler","name": "_handler","type": "address"}],"name": "setBeaconHandler","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [],"name": "stakingToken","outputs": [{"internalType": "contract ERC20Interface","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
            CustodyContractABI = """[{"inputs": [{"internalType": "address","name": "_withdrawalsOperator","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"anonymous": false,"inputs": [{"indexed": true,"internalType": "address","name": "user","type": "address"},{"indexed": true,"internalType": "address","name": "token","type": "address"},{"indexed": false,"internalType": "uint256","name": "amount","type": "uint256"},{"indexed": false,"internalType": "uint256","name": "nonce","type": "uint256"},{"indexed": false,"internalType": "bytes32","name": "hash","type": "bytes32"}],"name": "Deposited","type": "event"},{"anonymous": false,"inputs": [{"indexed": true,"internalType": "address","name": "oldOperator","type": "address"},{"indexed": true,"internalType": "address","name": "newOperator","type": "address"}],"name": "WithdrawalOperatorChanged","type": "event"},{"anonymous": false,"inputs": [{"indexed": true,"internalType": "address","name": "user","type": "address"},{"indexed": true,"internalType": "address","name": "token","type": "address"},{"indexed": false,"internalType": "uint256","name": "amount","type": "uint256"},{"indexed": false,"internalType": "uint256","name": "nonce","type": "uint256"},{"indexed": false,"internalType": "bytes32","name": "hash","type": "bytes32"}],"name": "Withdrawn","type": "event"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "__deposits","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes","name": "data","type": "bytes"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "__withdrawals","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes32","name": "","type": "bytes32"}],"name": "_deposits","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes","name": "data","type": "bytes"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes32","name": "","type": "bytes32"}],"name": "_withdrawals","outputs": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes","name": "_data","type": "bytes"}],"name": "bridgeFallBack","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "_newOperator","type": "address"}],"name": "changeWithdrawalOperator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "token","type": "address"},{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "bytes","name": "data","type": "bytes"}],"name": "deposit","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "bytes32","name": "_hash","type": "bytes32"}],"name": "deposits","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes","name": "data","type": "bytes"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"internalType": "struct CustodyManager.Deposit","name": "","type": "tuple"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "_index","type": "uint256"}],"name": "deposits","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "depositor","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes","name": "data","type": "bytes"},{"internalType": "bytes32","name": "hash","type": "bytes32"}],"internalType": "struct CustodyManager.Deposit","name": "","type": "tuple"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "depositsLength","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "address","name": "spender","type": "address"},{"internalType": "uint256","name": "_amount","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes","name": "_data","type": "bytes"}],"name": "receiveApproval","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [],"name": "totalDeposited","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "transferNonce","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "_index","type": "uint256"}],"name": "withdrawals","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"internalType": "struct CustodyManager.Withdrawal","name": "","type": "tuple"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "bytes32","name": "_hash","type": "bytes32"}],"name": "withdrawals","outputs": [{"components": [{"internalType": "uint256","name": "amount","type": "uint256"},{"internalType": "address","name": "withdrawer","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "address","name": "token","type": "address"},{"internalType": "bytes32","name": "hash","type": "bytes32"},{"internalType": "bool","name": "claimed","type": "bool"}],"internalType": "struct CustodyManager.Withdrawal","name": "","type": "tuple"}],"stateMutability": "view","type": "function"}]"""
            BeaconChainContractABI = """[{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_genesisBeacon","type": "tuple"},{"internalType": "contract StakeManager","name": "_stakingContract","type": "address"}],"stateMutability": "nonpayable","type": "constructor"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "beaconHash","outputs": [{"internalType": "bytes32","name": "beaconRoot","type": "bytes32"}],"stateMutability": "pure","type": "function"},{"inputs": [{"internalType": "uint256","name": "","type": "uint256"}],"name": "beacons","outputs": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"stateMutability": "view","type": "function"},{"inputs": [],"name": "chainLength","outputs": [{"internalType": "uint256","name": "","type": "uint256"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "address","name": "validator","type": "address"}],"name": "disableValidator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "address","name": "validator","type": "address"}],"name": "enableValidator","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [{"internalType": "uint256","name": "blockNumber","type": "uint256"}],"name": "getValidatorsAtBlock","outputs": [{"internalType": "address[]","name": "","type": "address[]"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "isBeaconValid","outputs": [{"internalType": "bool","name": "valid","type": "bool"},{"internalType": "string","name": "reason","type": "string"}],"stateMutability": "view","type": "function"},{"inputs": [{"internalType": "uint256","name": "blockNumber","type": "uint256"},{"internalType": "address","name": "valoper","type": "address"}],"name": "isValidatorAtBlock","outputs": [{"internalType": "bool","name": "","type": "bool"}],"stateMutability": "view","type": "function"},{"inputs": [{"components": [{"internalType": "address","name": "miner","type": "address"},{"internalType": "uint256","name": "nonce","type": "uint256"},{"internalType": "bytes[]","name": "messages","type": "bytes[]"},{"internalType": "uint256","name": "difficulty","type": "uint256"},{"internalType": "bytes32","name": "miningTarget","type": "bytes32"},{"internalType": "uint256","name": "timestamp","type": "uint256"},{"internalType": "bytes32","name": "parent","type": "bytes32"},{"internalType": "bytes32","name": "proof","type": "bytes32"},{"internalType": "uint256","name": "height","type": "uint256"},{"internalType": "bytes32","name": "son","type": "bytes32"},{"internalType": "uint8","name": "v","type": "uint8"},{"internalType": "bytes32","name": "r","type": "bytes32"},{"internalType": "bytes32","name": "s","type": "bytes32"}],"internalType": "struct BeaconChainHandler.Beacon","name": "_beacon","type": "tuple"}],"name": "pushBeacon","outputs": [],"stateMutability": "nonpayable","type": "function"},{"inputs": [],"name": "stakingContract","outputs": [{"internalType": "contract StakeManager","name": "","type": "address"}],"stateMutability": "view","type": "function"}]"""
            self.BEP20ABI = """[{"constant": true,"inputs": [],"name": "name","outputs": [{"name": "","type": "string"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": false,"inputs": [{"name": "_spender","type": "address"},{"name": "_value","type": "uint256"}],"name": "approve","outputs": [{"name": "","type": "bool"}],"payable": false,"stateMutability": "nonpayable","type": "function"},{"constant": true,"inputs": [],"name": "totalSupply","outputs": [{"name": "","type": "uint256"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": false,"inputs": [{"name": "_from","type": "address"},{"name": "_to","type": "address"},{"name": "_value","type": "uint256"}],"name": "transferFrom","outputs": [{"name": "","type": "bool"}],"payable": false,"stateMutability": "nonpayable","type": "function"},{"constant": true,"inputs": [],"name": "decimals","outputs": [{"name": "","type": "uint8"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": true,"inputs": [{"name": "_owner","type": "address"}],"name": "balanceOf","outputs": [{"name": "balance","type": "uint256"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": true,"inputs": [],"name": "symbol","outputs": [{"name": "","type": "string"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": false,"inputs": [{"name": "_to","type": "address"},{"name": "_value","type": "uint256"}],"name": "transfer","outputs": [{"name": "","type": "bool"}],"payable": false,"stateMutability": "nonpayable","type": "function"},{"constant": true,"inputs": [{"name": "_owner","type": "address"},{"name": "_spender","type": "address"}],"name": "allowance","outputs": [{"name": "","type": "uint256"}],"payable": false,"stateMutability": "view","type": "function"},{"payable": true,"stateMutability": "payable","type": "fallback"},{"anonymous": false,"inputs": [{"indexed": true,"name": "owner","type": "address"},{"indexed": true,"name": "spender","type": "address"},{"indexed": false,"name": "value","type": "uint256"}],"name": "Approval","type": "event"},{"anonymous": false,"inputs": [{"indexed": true,"name": "from","type": "address"},{"indexed": true,"name": "to","type": "address"},{"indexed": false,"name": "value","type": "uint256"}],"name": "Transfer","type": "event"}]"""
            self.cachedTokens = {}
            self.cachedDeposits = {}
            
            self.rpcurl = rpc
            self.chainID = 97
            self.cacheFile = cacheFile
            if (rpc.split(":")[0]) in ["ws", "wss"]:
                self.chain = Web3(Web3.WebsocketProvider(rpc))
            elif (rpc.split(":")[0]) in ["http", "https"]:
                self.chain = Web3(Web3.HTTPProvider(rpc))
            self.masterContract = self.chain.eth.contract(address=Web3.toChecksumAddress(MasterContractAddress), abi=MasterContractABI)
            # self.stakingContract = self.chain.eth.contract(address=self.masterContract.functions.staking().call(), abi=StakingContractABI)
            self.custodyContract = self.chain.eth.contract(address=self.masterContract.functions.custody().call(), abi=CustodyContractABI)
            # self.beaconChainContract = self.chain.eth.contract(address=self.masterContract.functions.beaconchain().call(), abi=BeaconChainContractABI)
            self.loadCacheFile()
            
            
        def getDepositDetails(self, _hash):
            if self.cachedDeposits.get(_hash):
                print(f"Deposit {_hash} pulled from cache")
                return self.cachedDeposits.get(_hash).legacyFormat
            cachedDeposit = self.CachedDeposit(depositData=self.custodyContract.functions.deposits(_hash).call())
            # if (w3.toChecksumAddress(self.token) != w3.toChecksumAddress(returnValue["token"])):
                # returnValue["amount"] = 0
            self.cachedDeposits[_hash] = cachedDeposit
            print(f"Deposit {_hash} pulled from BSC")
            self.saveCacheFile()
            return cachedDeposit.legacyFormat
            
        def getBEP20At(self, addr):
            if self.cachedTokens.get(addr):
                return self.cachedTokens[addr]
            _cached = self.CachedToken(self.chain.eth.contract(address=Web3.toChecksumAddress(addr), abi=self.BEP20ABI))
            self.cachedTokens[addr] = _cached
            self.saveCacheFile()
            return _cached
                        
        def serializeCachedTokens(self):
            done = {}
            for address, token in self.cachedTokens.items():
                done[address] = token.JSONSerializable()
            return done
            
        def loadCachedTokens(self, data):
            for address, cached in data.items():
                self.cachedTokens[address] = self.CachedToken(self.chain.eth.contract(address=Web3.toChecksumAddress(address), abi=self.BEP20ABI), cached)
            
        def serializeCachedDeposits(self):
            returnValue = {}
            for key, value in self.cachedDeposits.items():
                returnValue[key] = value.JSONSerializable()
            return returnValue
            
        def loadCachedDeposits(self, data):
            for key, value in data.items():
                self.cachedDeposits[int(key) if key.isnumeric() else key] = self.CachedDeposit(cacheData=value)
            
        def loadCacheFile(self):
            if not self.cacheFile:
                return
            f = open(self.cacheFile, "r")
            _data = json.load(f)
            f.close()
            self.loadCachedTokens(_data.get("tokens", {}))
            self.loadCachedDeposits(_data.get("deposits", {}))
            
            
        def saveCacheFile(self):
            if not self.cacheFile:
                return
            f = open(self.cacheFile, "w")
            _data = json.dumps({"tokens": self.serializeCachedTokens(), "deposits": self.serializeCachedDeposits()})
            f.write(_data)
            f.close()


    class GenesisBeacon(object):
        def __init__(self, testnet=True):
            if testnet:
                self.timestamp = 1645457628
                self.miner = "0x0000000000000000000000000000000000000000"
                self.parent = "Initializing the RaptorChain...".encode()
                self.difficulty = 1
                self.decodedMessages = ["Hey guys, just trying to implement a kind of raptor chain, feel free to have a look".encode()]
                self.messages = eth_abi.encode_abi(["bytes[]"], [self.decodedMessages])
                self.nonce = 0
                self.miningTarget = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
                self.proof = self.proofOfWork()
            else:
                self.timestamp = 1654884714
                self.miner = "0x0000000000000000000000000000000000000000"
                self.parent = b"RaptorChain Mainnet almost ready"
                self.difficulty = 1
                self.decodedMessages = [b"Hey guys, I'm working on RaptorChain and expecting it to work very soon !!! - 10/06/2022"]
                self.messages = eth_abi.encode_abi(["bytes[]"], [self.decodedMessages])
                self.nonce = 0
                self.miningTarget = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
                self.proof = self.proofOfWork()
            self.parentTxRoot = "0x0000000000000000000000000000000000000000000000000000000000000000"
            self.stateRoot = "0x0000000000000000000000000000000000000000000000000000000000000000"
            self.transactions = []
            self.depCheckerTxs = []
            self.son = ""
            self.number = 0
            self.nextBlockTx = None
            self.v = 0
            self.r = "0x0000000000000000000000000000000000000000000000000000000000000000"
            self.s = "0x0000000000000000000000000000000000000000000000000000000000000000"
            self.sig = "0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            self.relayerSigs = []
            
        def beaconRoot(self):
            messagesHash = w3.keccak(eth_abi.encode_abi(["bytes[]"], [self.decodedMessages]))
            bRoot = w3.soliditySha3(["bytes32", "uint256", "bytes","address"], [self.parent, self.timestamp, messagesHash, self.miner]) # parent PoW hash (bytes32), beacon's timestamp (uint256), beacon miner (address)
            return bRoot.hex()

        def proofOfWork(self):
            bRoot = self.beaconRoot()
            proof = w3.soliditySha3(["bytes32", "uint256"], [bRoot, int(self.nonce)])
            return proof.hex()

        def messagesToHex(self):
            _msgs = []
            for _msg_ in self.decodedMessages:
                _msgs.append(f"0x{_msg_.hex()}")
            return _msgs

        def difficultyMatched(self):
            return int(self.proofOfWork(), 16) < self.miningTarget

        def ABIEncodable(self):
            return ([self.miner, int(self.nonce),[f"0x{m.hex()}" for m in self.decodedMessages],int(self.difficulty), self.miningTarget, int(self.timestamp), ("0x" + ((self.parent + (b'\x00' * (32-len(self.parent)))).hex())), self.proof, int(self.number), "0x0000000000000000000000000000000000000000000000000000000000000000", self.parentTxRoot, int(self.v), self.r, self.s, [f"0x{s.hex()}" for s in self.relayerSigs]])

        # def exportJson(self):
            # return {"transactions": self.transactions, "messages": self.messages.hex(), "parent": self.parent.hex(), "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}}

        def txsRoot(self):
            return w3.solidityKeccak(["bytes32", "bytes32", "bytes32[]"], [self.proof, self.stateRoot, sorted(self.transactions)])

        def exportJson(self):
            return {"transactions": (self.depCheckerTxs + self.transactions + [self.nextBlockTx]), "txsRoot": self.txsRoot().hex(), "messages": self.messages.hex(), "decodedMessages": self.messagesToHex(), "parentTxRoot": self.parentTxRoot, "parent": self.parent.hex(), "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}, "signature": {"v": self.v, "r": self.r, "s": self.s, "sig": self.sig}}


    class Beacon(object):
        # def __init__(self, parent, difficulty, timestamp, miner, logsBloom):
            # self.miner = ""
            # self.timestamp = timestamp
            # self.parent = parent
            # self.nonce = nonce
            # self.logsBloom = logsBloom
            # self.miner = w3.toChecksumAddress(miner)
            # self.difficulty = difficulty
            # self.miningTarget = int((2**256)/self.difficulty)
            # self.proof = self.proofOfWork()
        
        def __init__(self, data, difficulty, stateRoot="0x0000000000000000000000000000000000000000000000000000000000000000"):
            miningData = data["miningData"]
            self.depCheckerTxs = []
            self.miner = w3.toChecksumAddress(miningData["miner"])
            self.parentTxRoot = data.get("parentTxRoot", "0x0000000000000000000000000000000000000000000000000000000000000000")
            self.nonce = miningData["nonce"]
            self.difficulty = difficulty
            self.messages = bytes.fromhex(data['messages'].replace('0x', ''))
            self.decodedMessages = list(eth_abi.decode_abi(["bytes[]"], bytes.fromhex(data["messages"].replace("0x", "")))[0])
            self.miningTarget = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
            self.stateRoot = stateRoot
            self.timestamp = int(data["timestamp"])
            self.parent = data["parent"]
            self.transactions = []
            self.proof = self.proofOfWork()
            self.number = 0
            self.son = ""
            self.nextBlockTx = None
            self.v = data["signature"]["v"]
            self.r = data["signature"]["r"]
            self.s = data["signature"]["s"]
            self.sig = data["signature"]["sig"]
        

        def beaconRoot(self):
            messagesHash = w3.soliditySha3(["bytes"], [self.messages])
            bRoot = w3.soliditySha3(["bytes32", "uint256", "bytes32", "bytes32","address"], [self.parent, int(self.timestamp), messagesHash, self.parentTxRoot, self.miner]) # parent PoW hash (bytes32), beacon's timestamp (uint256), hash of messages (bytes32), beacon miner (address)
            return bRoot.hex()

        def proofOfWork(self):
            bRoot = self.beaconRoot()
    #        print(f"Beacon root : {bRoot}")
            proof = w3.solidityKeccak(["bytes32", "uint256"], [bRoot, int(self.nonce)])
            return proof.hex()

        def difficultyMatched(self):
            return int(self.proofOfWork(), 16) < int(self.miningTarget, 16)

        def signatureMatched(self):
            print(f"Block proof : {self.proof}")
            print(f"Signer : {w3.eth.account.recoverHash(self.proof, vrs=(self.v, self.r, self.s))}")
            print(f"Miner : {self.miner}")
            return (w3.eth.account.recoverHash(self.proof, vrs=(self.v, self.r, self.s)) == self.miner)

        def messagesToHex(self):
            _msgs = []
            for _msg_ in self.decodedMessages:
                _msgs.append(f"0x{_msg_.hex()}")
            return _msgs

        def txsRoot(self):
            return w3.solidityKeccak(["bytes32", "bytes32", "bytes32[]"], [self.proof, self.stateRoot, sorted(self.transactions)])

        def ABIEncodable(self):
            return ([self.miner, int(self.nonce),[f"0x{m.hex()}" for m in self.decodedMessages],int(self.difficulty), self.miningTarget, int(self.timestamp), self.parent, self.proof, int(self.number), "0x0000000000000000000000000000000000000000000000000000000000000000", self.parentTxRoot, int(self.v), self.r, self.s, [f"0x{s.hex()}" for s in self.relayerSigs]])

        def exportJson(self):
            # return {"transactions": self.transactions, "messages": self.messages.hex(), "decodedMessages": self.messagesToHex(), "parent": self.parent, "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}, "signature": {"v": self.v, "r": self.r, "s": self.s, "sig": self.sig}, "ABIEncodableTuple": self.ABIEncodableTuple()}
            return {"transactions": (self.depCheckerTxs + self.transactions + [self.nextBlockTx]), "txsRoot": self.txsRoot().hex(),"messages": self.messages.hex(), "parentTxRoot": self.parentTxRoot, "decodedMessages": self.messagesToHex(), "parent": self.parent, "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}, "signature": {"v": self.v, "r": self.r, "s": self.s, "sig": self.sig}}


    def __init__(self):
        self.difficulty = 1
        self.miningTarget = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        self.blocks = [self.GenesisBeacon()]
        self.blocksByHash = {self.blocks[0].proof: self.blocks[0]}
        self.pendingMessages = []
        self.blockReward = 0
        self.blockTime = 600 # in seconds
        self.validators = {"0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846": self.Masternode("0x0000000000000000000000000000000000000000", "0x6Ff24B19489E3Fe97cfE5239d17b745D4cEA5846")}
        self.defaultMessage = eth_abi.encode_abi(["address", "uint256", "bytes"], ["0x0000000000000000000000000000000000000000", 0, b""])
        self.bsc = self.BSCInterface("https://data-seed-prebsc-2-s1.binance.org:8545/", "0x723b074d5f653CbFCe78752DEC34301a3EA8326F", "0xC64518Fb9D74fabA4A748EA1Db1BdDA71271Dc21")
        self.STIUpgradeBlock = 1

    def checkBeaconMessages(self, beacon):
        _messages = beacon.decodedMessages.copy()
        if (not len(_messages)):
            return False
        for msg in _messages:
            if (not (msg in self.pendingMessages)):
                return False
        return True
    
    def calcDifficulty(self, expectedDelay, timestamp1, timestamp2, currentDiff):
        return min(max((currentDiff * expectedDelay)/max((timestamp2 - timestamp1), 1), currentDiff * 0.9, 1), currentDiff*1.1)
    
    def isBeaconValid(self, beacon):
        _lastBeacon = self.getLastBeacon()
        if _lastBeacon.proof != beacon.parent:
            return (False, "UNMATCHED_BEACON_PARENT")
        if not self.checkBeaconMessages(beacon):
            return (False, "INVALID_MESSAGE")
        if not beacon.signatureMatched():
            return (False, "UNMATCHED_SIGNATURE")
        # if (not self.bsc.beaconChainContract.functions.isValidatorAtBlock(len(self.blocks), w3.toChecksumAddress(beacon.miner))):
            # return (False, "NOT_A_MASTERNODE")
        if not self.validators.get(w3.toChecksumAddress(beacon.miner)):
            return (False, "NOT_IN_VALIDATOR_SET")
        # if (beacon.miner == _lastBeacon.miner):
            # return (False, "ALREADY_PRODUCED_LAST_BEACON")
        if ((int(beacon.timestamp) < (int(_lastBeacon.timestamp)+int(self.blockTime))) or (beacon.timestamp > time.time())):
            return (False, "INVALID_TIMESTAMP")
        if ((len(self.blocks) < self.STIUpgradeBlock) or (beacon.parentTxRoot == self.blocks[len(self.blocks)-1].txsRoot())):
            return (False, "STI_UPGRADE_UNMATCHED")
        if (not len(self.pendingMessages)):
            return (False, "NO_DATA_HERE")
        return (True, "GOOD")
    
    
    def isBlockValid(self, blockData):
        try:
            return self.isBeaconValid(self.Beacon(blockData, self.difficulty))
        except Exception as e:
            return (False, e)
    
    def getLastBeacon(self):
        return self.blocks[len(self.blocks) - 1]
    
    def addBeaconToChain(self, beacon):
        _messages = beacon.decodedMessages.copy()
        for msg in _messages:
            if msg != self.defaultMessage:
                self.pendingMessages.remove(msg)
        currentChainLength = len(self.blocks)
        self.getLastBeacon().son = beacon.proof
        _oldtimestamp = self.getLastBeacon().timestamp
        beacon.number = currentChainLength
        self.blocks.append(beacon)
        self.blocksByHash[beacon.proof] = beacon
        # self.difficulty = self.calcDifficulty(self.blockTime, _oldtimestamp, int(beacon.timestamp), self.difficulty)
        # self.miningTarget = hex(int(min(int((2**256-1)/self.difficulty),0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)))
        return True
    
    def submitBlock(self, block):
        # print(block)
        try:
            _beacon = self.Beacon(block, self.difficulty)
        except Exception as e:
            print(f"Exception submitting a block : {e}")
            return False
        beaconValidity = self.isBeaconValid(_beacon)
        if beaconValidity[0]:
            self.addBeaconToChain(_beacon)
            return _beacon.miner
        return False
    
    def mineEpoch(self, epochDetails):
        isValid = self.isEpochValid(epochDetails)
    
    
    def submitMessage(self, message):
        self.pendingMessages.append(message)
    
    def getBlockByHeightJSON(self, height):
        try:
            return self.blocks[height].exportJson()
        except Exception as e:
            print(f"Exception happened while pulling block {height}: {e.__repr__()}")
            return None
    
    def getLastBlockJSON(self):
        return self.getLastBeacon().exportJson()
    
    def exportMempool(self):
        _msgs_  = []
        for _msg in self.pendingMessages:
            _msgs_.append(_msg.hex())
        return _msgs_
    
    def postMessage(self, to, data):
        self.pendingMessages.append(eth_abi.encode_abi(["address", "uint256", "bytes"], [self.bsc.custodyContract.address, self.bsc.chainID, data]))
#			(recipient, chainID, data) = abi.decode(_beacon.messages[n], (address, uint256, bytes));
    
    def createValidator(self, owner, operator):
        if not self.validators.get(operator):
            self.validators[operator] = self.Masternode(owner, operator)
    
    def destroyValidator(self, operator):
        if self.validators.get(operator):
            del self.validators[operator]
            
    def validatorSetHash(self):
        valHashes = []
        for op, val in self.validators.items():
            valHashes.append(val.hash)
        return w3.solidityKeccak(["bytes32[]"], [sorted(valHashes)])
    
    def updateStateRoot(self, newRoot):
        self.stateRoot = newRoot
        self.getLastBeacon().stateRoot = newRoot
    
    def JSONSerializable(self):
        blocksJSON = []
        valsJSON = []
        hashToHeight = {}
        for block in self.blocks:
            blocksJSON.append(block.exportJson())
            hashToHeight[block.proof] = block.number
        for op, val in self.validators.items():
            valsJSON.append(val.JSONSerializable())
        return {"blocks": blocksJSON, "hashToHeight": hashToHeight, "mempool": [m.hex() for m in self.pendingMessages], "validators": valsJSON, "difficulty": self.difficulty, "miningTarget": self.miningTarget}

class State(object):
    class Account(object):
        def __init__(self, address, initTxID, accountGetter, callfallback, chainAccess, snapshotData={}):
            self.address = w3.toChecksumAddress(address)
            self.initialized = False
            self.balance = snapshotData.get("balance", 0)
            self.tempBalance = snapshotData.get("tempBalance", 0)
            self.transactions = snapshotData.get("transactions", [initTxID])
            self.sent = snapshotData.get("sent", [initTxID])
            self.received = snapshotData.get("received", [])
            self.mined = snapshotData.get("mined", [])
            self.bio = snapshotData.get("bio", "")
            self.code = bytes.fromhex(snapshotData.get("code", ""))
            self.storage = snapshotData.get("storage", {})
            self.tempStorage = snapshotData.get("tempStorage", {})
            self.hash = ""
            self.calcHash(False)
            self.defaultHash = snapshotData.get("defaultHash", self.hash)
            self.precompiledContract = None
            self.accountGetter = accountGetter
            self.callfallback = callfallback
            self.chainAccess = chainAccess
            self.opcodes = EVM.Opcodes().opcodes
            self.debug = False
            
        def serializeEVMStorage(self):
            btarr = b""
            for key, value in sorted(self.storage.items()):
                if value > 0:
                    btarr = (btarr + int(key).to_bytes(32, "big") + int(key).to_bytes(32, "big"))
            return btarr

        def setPrecompiledContract(self, contract, initialize):
            self.precompiledContract = contract
            if not initialize:
                self.initialized = False
            
        def calcHash(self, init=True):
            if init:
                self.initialized = True
            storageHash = w3.keccak(self.serializeEVMStorage())
            codeHash = w3.keccak(self.code)
            historyHash = w3.solidityKeccak(["bytes32[]", "bytes32[]"], [self.transactions[1:], self.sent[1:]])
            self.hash = w3.solidityKeccak(["address", "uint256", "bytes32", "bytes32", "bytes32", "string"], [self.address, self.balance, historyHash, codeHash, storageHash, self.bio])
            return self.hash
        
        def makeChangesPermanent(self):
            self.storage = self.tempStorage.copy()
            self.balance = self.tempBalance
        
        def cancelChanges(self):
            self.tempStorage = self.storage.copy()
            self.tempBalance = self.balance

        def addParent(self, txid):
            if (self.transactions[len(self.transactions)-1] != txid):
                self.transactions.append(txid)
        
        def isInitialized(self):
            return (self.hash == self.defaultHash)
        
        def _prepareCallEnv(self, msg):
            return EVM.CallEnv(self.accountGetter, caller=msg.sender, runningAccount=self, recipient=self.address, beaconchain=self.chainAccess, value=msg.value, gaslimit=msg.gas, tx=msg.tx, data=msg.data, callfallback=self.callfallback, code=b"", static=False, storage=None, calltype=msg.calltype, calledFromAcctClass=True)
        
        def _execStandardCall(self, env, persist=False):
            if not len(self.code):
                return
            while True and (not env.halt):
                try:
                    if self.debug:
                        op = self.code[env.pc]
                        history.append(hex(op))
                        self.opcodes[op](env)
                        debugfile.write(f"Program Counter : {env.pc} - last opcode : {hex(op)} - stack : {env.stack} - lastRetValue : {env.lastCallReturn} - memory : {bytes(env.memory.data)} - storage : {env.storage} - remainingGas : {env.remainingGas()} - success : {env.getSuccess()} - halted : {env.halt}\n")
                    else:
                        self.opcodes[self.code[env.pc]](env)
                except Exception as e:
                    raise
            if (env.calltype == 3) or (env.tx.contractDeployment):
                self.makeChangesPermanent()
                if persist:
                    self.code = env.returnValue
        
        
        def call(self, msg):
            env = self._prepareCallEnv(msg)
            history = []
            if self.precompiledContract:
                print("Executing call as precompiled")
                self.precompiledContract.call(env)
            else:
                print("Executing call as standard")
                self._execStandardCall(env, msg.persistStorage)
            if msg.persistStorage:
                self.tempStorage = msg.storage
            return env
        
        def JSONSerializable(self):
            return {"balance": self.balance, "tempBalance": self.tempBalance, "transactions": self.transactions, "sent": self.sent, "received": self.received, "mined": self.mined, "bio": self.bio, "code": self.code.hex(), "storage": self.storage, "tempStorage": self.tempStorage, "hash": self.hash.hex(), "defaultHash": self.defaultHash, "initialized": self.initialized}

    class CallBlankTransaction(object):
        def __init__(self, call):
            self.contractDeployment = False
            self.sender = w3.toChecksumAddress(call.get("from", "0x0000000000000000000000000000000000000000"))
            self.recipient = w3.toChecksumAddress(call.get("to", "0x0000000000000000000000000000000000000000"))
            if (self.recipient == "0x0000000000000000000000000000000000000000"):
                self.contractDeployment = True
            self.value = call.get("value", 0)
            self.value = self.value if type(self.value) == int else ((int(self.value, 16) if "0x" in self.value else int(self.value)) if type(self.value == str) else 0)
            try:
                _data = call.get("data", "0x")
                self.data = _data if type(_data) == bytes else bytes.fromhex(_data.replace("0x", ""))
            except:
                self.data = b""
            self.gasprice = call.get("gasprice", 0)
            self.gasLimit = call.get("gas", 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)
            self.txid = "0x8c7e29b8d1ee82f7d7399a7d9aabd93fb07b5bb0274d2b564ce42afa73560524"
            self.affectedAccounts = [self.sender, self.recipient]

        def formatAddress(self, _addr):
            if (type(_addr) == int):
                hexfmt = hex(_addr)[2:]
                return w3.toChecksumAddress("0x" + ("0" * (40-len(hexfmt))) + hexfmt)
            return w3.toChecksumAddress(_addr)

        def markAccountAffected(self, addr):
            _addr = self.formatAddress(addr)
            if not _addr in self.affectedAccounts:
                self.affectedAccounts.append(_addr)


    def __init__(self, initTxID):
        self.messages = {}
        self.opcodes = EVM.Opcodes().opcodes
        self.initTxID = initTxID
        self.txChilds = {self.initTxID: []}
        self.txIndex = {}
        self.lastTxIndex = 0
        self.beaconChain = BeaconChain()
        self.holders = ["0x3f119Cef08480751c47a6f59Af1AD2f90b319d44", "0x611B74e0dFA8085a54e8707c573A588138c9dDba", "0x0000000000000000000000000000000000000000"]
        self.totalSupply = 0
        self.type2ToType0Hash = {}
        self.type0ToType2Hash = {}
        self.processedL2Hashes = []
        self.accounts = {"0x0000000000000000000000000000000000000000": self.Account("0x0000000000000000000000000000000000000000", self.initTxID, self.getAccount, self.executeChildCall, self.beaconChain), "0x0000000000000000000000000000000000000001": self.Account("0x0000000000000000000000000000000000000001", self.initTxID, self.getAccount, self.executeChildCall, self.beaconChain)}
        self.crossChainAddress = "0x0000000000000000000000000000000000000097"
        self.lastIndex = 0
        self.accounts["0x0000000000000000000000000000000000000001"].code = bytes.fromhex("608060405234801561001057600080fd5b506004361061002b5760003560e01c806357ecc14714610030575b600080fd5b61003861004e565b60405161004591906100c4565b60405180910390f35b60606040518060400160405280600b81526020017f48656c6c6f20776f726c64000000000000000000000000000000000000000000815250905090565b6000610096826100e6565b6100a081856100f1565b93506100b0818560208601610102565b6100b981610135565b840191505092915050565b600060208201905081810360008301526100de818461008b565b905092915050565b600081519050919050565b600082825260208201905092915050565b60005b83811015610120578082015181840152602081019050610105565b8381111561012f576000848401525b50505050565b6000601f19601f830116905091905056fea2646970667358221220ad44bfb067953d1048acb02d7ee13b978ad64129db11c038ac3f4c82c858f71f64736f6c63430007060033")
        self.receipts = {}
        self.precompiledContractsHandler = EVM.PrecompiledContracts(self.crossChainFallback, self.beaconChain.bsc, self.getAccount)
        self.precompiledContracts = self.precompiledContractsHandler.contracts
        self.hash = ""
        self.debug = False
        self.shouldLog = True
        self.chainID = 499597202514
        self.version = "0.5.0-testnet"

    def formatAddress(self, _addr):
        if (type(_addr) == int):
            hexfmt = hex(_addr)[2:]
            return w3.toChecksumAddress("0x" + ("0" * (40-len(hexfmt))) + hexfmt)
        return w3.toChecksumAddress(_addr)

    def getAccount(self, _addr, skipInit=False):
        chkaddr = self.formatAddress(_addr)
        if not skipInit:
            self.ensureExistence(chkaddr)
        return self.accounts.get(chkaddr, self.Account(chkaddr, self.initTxID, self.getAccount, self.executeChildCall, self.beaconChain))

    def calcStateRoot(self):
        accountHashes = []
        for (addr, acct) in self.accounts.items():
            if acct.isInitialized():
                accountHashes.append(acct.hash)
        accountingRoot = w3.solidityKeccak(["bytes32[]"], [sorted(accountHashes)])
        masternodesRoot = self.beaconChain.validatorSetHash()
        self.hash = w3.solidityKeccak(["bytes32", "bytes32"], [accountingRoot, masternodesRoot])
        self.beaconChain.updateStateRoot(self.hash)
        return self.hash
        

    def log(self, data):
        if self.shouldLog:
            print(data)

    def getCurrentEpoch(self):
        return self.beaconChain.getLastBeacon().proof
        
    def getGenesisEpoch(self):
        return self.beaconChain.blocks[0].proof

    def ensureExistence(self, _user):
        user = self.formatAddress(_user)
        if not self.accounts.get(user):
            print(f"Created account {user}")
            self.accounts[user] = self.Account(user, self.initTxID, self.getAccount, self.executeChildCall, self.beaconChain)

    def checkParent(self, tx):
        lastTx = self.getLastUserTx(tx.sender)
        if tx.txtype == 6:
            return True
        if tx.epoch != self.beaconChain.blocks[len(self.beaconChain.blocks)-1].proof:
            return False
        if tx.txtype == 2:
            try:
                tx.parent = self.getAccount(tx.sender).sent[tx.nonce - 1]
            except:
                pass
#                raise
            return (tx.nonce == len(self.getAccount(tx.sender).sent))
        else:
            return (tx.parent == lastTx)

    def checkBalance(self, tx):
        return (tx.value+tx.fee) > (self.getAccount(tx.sender).balance)

    def isBeaconCorrect(self, tx):
        # print(tx.epoch)
        return (tx.epoch == self.getCurrentEpoch())



    
    def estimateTransferSuccess(self, _tx):
        self.ensureExistence(_tx.sender)
        self.ensureExistence(_tx.recipient)
        if self.checkBalance(_tx):
            return (False, "Too low balance")
        if not self.checkParent(_tx):
            return (False, "Parent unmatched")
            
        return (True, "It'll succeed")

    def estimateMiningSuccess(self, tx):
        self.ensureExistence(tx.sender)
        return self.beaconChain.isBlockValid(tx.blockData)

    def estimateDepositSuccess(self, _tx):
        return ((not _tx.l2hash in self.processedL2Hashes), "Checking if it's already processed")

    def estimateCreateMNSuccess(self, tx):
        _sufficientBalance = (self.getAccount(tx.sender).balance >= 1000000000000000000000000) # 1 million with 18 decimals
        _canAddToSet = (not (self.beaconChain.validators.get(tx.recipient)))
        return (_sufficientBalance and _canAddToSet)
    
    def estimateDestroyMNSuccess(self, tx):
        if ((not (self.beaconChain.validators.get(tx.recipient)))):
            return False
        return (self.beaconChain.validators.get(tx.recipient).owner == tx.sender)
        
    def createMN(self, tx):
        willSucceed = self.estimateCreateMNSuccess(tx)
        if not willSucceed:
            return False
        self.getAccount(tx.sender).balance -= 1000000000000000000000000
        self.beaconChain.createValidator(tx.sender, tx.recipient)
    
    def destroyMN(self, tx):
        if not self.estimateDestroyMNSuccess(self, tx):
            return False
        self.getAccount(self.beaconChain.validators.get(tx.recipient).owner).balance += 1000000000000000000000000
        self.beaconChain.destroyValidator(tx.recipient)
    

    # def checkOutDeposit(self, tx):
        # if not tx.l2hash in self.processedL2Hashes:
            # depositInfo = self.beaconChain.bsc.getDepositDetails(tx.l2hash)
            # self.accounts[depositInfo["depositor"]].balance += depositInfo["amount"]
            # self.totalSupply += depositInfo["amount"]
            # # if tx.sender != depositInfo["depositor"]:
                # # self.accounts[depositInfo["depositor"]].transactions.append(tx.txid)
            # self.accounts[depositInfo["depositor"]].transactions.append(tx.txid)
            # self.processedL2Hashes.append(depositInfo["hash"])
            # return (True, f"Deposited {depositInfo['amount']} to {depositInfo['depositor']}")
        # else:
            # return (False, "Already processed")

    def calcBridgedTokenAddress(self, chainID, token):
        return w3.toChecksumAddress(hex(int(token, 16) + chainID))

    def checkOutDepositByIndex(self, tx, _index):
        depositInfo = self.beaconChain.bsc.getDepositDetails(int(_index))
        if not depositInfo["hash"] in self.processedL2Hashes:
            self.ensureExistence(depositInfo["depositor"])
            
            print(depositInfo)
            if (depositInfo["token"] == self.beaconChain.bsc.token):
                self.accounts[depositInfo["depositor"]].balance += depositInfo["amount"]
                self.accounts[depositInfo["depositor"]].tempBalance += depositInfo["amount"]
                print(f"Depositing {depositInfo['amount']} to {depositInfo['depositor']}")
                self.totalSupply += depositInfo["amount"]
            else:
                _calculatedAddress = self.precompiledContractsHandler.calcBridgedAddress(depositInfo["token"])
                env = EVM.CallEnv(self.getAccount, self.crossChainAddress, self.getAccount(_calculatedAddress), _calculatedAddress, self.beaconChain, 0, 69000, tx, b"", self.executeChildCall, b"", False, calltype=1)
                self.precompiledContractsHandler.mintCrossChainToken(env, depositInfo["token"], depositInfo['depositor'], depositInfo["amount"])
                if env.getSuccess():
                    env.getAccount(_calculatedAddress).tempStorage = env.storage.copy()
                    env.getAccount(_calculatedAddress).makeChangesPermanent()
            # if tx.sender != depositInfo["depositor"]:
                # transactions[depositInfo["depositor"]].append(tx.txid)
            self.accounts[depositInfo["depositor"]].transactions.append(f"0x{depositInfo['hash'].hex()}")
            self.processedL2Hashes.append(depositInfo["hash"])
            self.txChilds[f"0x{depositInfo['hash'].hex()}"] = []
            self.accounts[depositInfo["depositor"]].calcHash()
            return (True, f"Deposited {depositInfo['amount']} to {depositInfo['depositor']}")
        else:
            return (False, "Already processed")

    def checkDepositsTillIndex(self, tx):
        maxIndex = tx.indexToCheck
        _lastindex = self.lastIndex
        for i in range(_lastindex, maxIndex):
            try:
                self.checkOutDepositByIndex(tx, i)
            except Exception as e:
                print(e)
                pass
            self.lastIndex = i+1

    def updateHolders(self):
        _holders = []
        for key, value in self.accounts.items():
            if value.balance > 0:
                _holders.append(key)
        self.holders = _holders

    def createSmartContract(self, tx):
        pass
    

    def willTransactionSucceed(self, tx):
        _tx = Transaction(tx)
        underlyingOperationSuccess = (False, None)
        correctParent = self.checkParent(_tx)
        correctBeacon = self.isBeaconCorrect(_tx)
        if _tx.txtype == 0:
            underlyingOperationSuccess = self.estimateTransferSuccess(_tx)
        if _tx.txtype == 1:
            underlyingOperationSuccess = self.estimateMiningSuccess(_tx)
        if _tx.txtype == 2:
            underlyingOperationSuccess = self.tryContractCall(_tx)
        if _tx.txtype == 3:
            underlyingOperationSuccess = self.estimateDepositSuccess(_tx)
            # underlyingOperationSuccess = (True, "Better to show True")
        if _tx.txtype == 4:
            underlyingOperationSuccess = self.estimateCreateMNSuccess(_tx)
        if _tx.txtype == 5:
            underlyingOperationSuccess = self.estimateDestroyMNSuccess(_tx)
        if _tx.txtype == 6:
            underlyingOperationSuccess = (True, None)
        print(correctBeacon, correctParent, underlyingOperationSuccess)
        return (underlyingOperationSuccess[0] and correctBeacon and correctParent)
        

    # def mineBlock(self, blockData):
        # self.beaconChain.submitBlock(blockData)



    def applyParentStuff(self, tx):
        self.txChilds[tx.txid] = []
        if tx.txtype == 2:
            tx.parent = self.getAccount(tx.sender).sent[tx.nonce - 1]
            self.type2ToType0Hash[tx.ethTxid] = tx.txid
            self.type0ToType2Hash[tx.txid] = tx.ethTxid
            # print(tx.parent)
            
        if self.beaconChain.blocksByHash.get(tx.epoch):
            if tx.txtype != 1:
                if not tx.txid in self.beaconChain.blocksByHash[tx.epoch].transactions:
                    self.beaconChain.blocksByHash[tx.epoch].transactions.append(tx.txid)
            else:
                self.beaconChain.blocksByHash[tx.epoch].nextBlockTx = tx.txid
        else:
            return False
            
        self.txChilds[tx.parent].append(tx.txid)
        self.txIndex[tx.txid] = self.lastTxIndex
        self.lastTxIndex += 1
        self.accounts[tx.sender].sent.append(tx.txid)
        if tx.txtype == 2:
            return
        if tx.txtype == 1:
            miner = self.formatAddress(tx.blockData.get("miningData").get("miner"))
            self.ensureExistence(miner)
            self.accounts[miner].mined.append(tx.txid)
            tx.affectedAccounts.append(miner)
            # self.accounts[miner].transactions.append(tx.txid)
        
        self.accounts[tx.recipient].received.append(tx.txid)


    def crossChainFallback(self, recipient, token, user, value, nonce):
        encodedData = eth_abi.encode_abi(["address", "address", "uint256", "uint256"], [token, user, value, nonce]) # decoder on solidity side : (address token, address withdrawer, uint256 amount, uint256 nonce) = abi.decode(_data, (address, address, uint256, uint256));
        recipient = recipient
        return (recipient, encodedData)
        

    def requestCrosschainTransfer(self, tx):
        encodedData = eth_abi.encode_abi(["address", "address", "uint256", "uint256"], [self.beaconChain.bsc.token, tx.sender, int(tx.value), len(self.accounts[tx.sender].transactions)]) # decoder on solidity side : (address token, address withdrawer, uint256 amount, uint256 nonce) = abi.decode(_data, (address, address, uint256, uint256));
        self.beaconChain.postMessage(self.beaconChain.bsc.custodyContract.address, encodedData)
        print(f"Initiated cross-chain transfer of {tx.value/10**18}RPTR")
    
    def postTxMessages(self, tx):
        for msg in tx.messages:
            self.beaconChain.postMessage(msg[0], msg[1])

    def executeTransfer(self, tx, showMessage):
        willSucceed = self.estimateTransferSuccess(tx)
        if not willSucceed[0]:
            return willSucceed
        self.applyParentStuff(tx)
        
        
        self.accounts[tx.sender].balance -= (tx.value + tx.fee)
        self.accounts[self.beaconChain.blocksByHash.get(tx.epoch).miner].balance += tx.fee
        if (tx.recipient == self.crossChainAddress):
            self.requestCrosschainTransfer(tx)
            self.totalSupply -= tx.value
        else:
            self.accounts[tx.recipient].balance += tx.value
        
        if (showMessage):
            print(f"Transfer executed !\nAmount transferred : {(tx.value/(10**18))} RPTR\nFrom: {tx.sender}\nTo: {tx.recipient}")
        return (True, "Transfer succeeded")

    def mineBlock(self, tx):
        try:
            self.ensureExistence(tx.sender)
            feedback = self.beaconChain.submitBlock(tx.blockData);
            self.applyParentStuff(tx)
            if feedback:
                self.accounts[feedback].balance += self.beaconChain.blockReward
                self.totalSupply += self.beaconChain.blockReward
                return True
            return False
        except:
            raise
            return False

    def ecRecover(self, env):
        sig = env.data[63:]
        try:
            recovered = w3.eth.account.recoverHash(env.data[0:32], vrs=(sig[0], sig[1:33], sig[33:65]))
        except:
            recovered = "0x0000000000000000000000000000000000000000"
        env.returnValue = int(recovered, 16).to_bytes(32, "big")
        # print(f"Called ecRecover with sig {sig} and hash {env.data[0:32]}, returnValue : {env.returnValue}")

    def execEVMCall(self, env):
        if self.precompiledContracts.get(env.runningAccount.address):
            self.precompiledContracts.get(env.runningAccount.address).call(env)
            return
        history = []
        if self.debug:
            debugfile = open(f"raptorevmdebug-{env.tx.txid}.log", "w")
            debugfile.write(f"Calldata : {env.data}\nmsg.sender address : {env.msgSender}\naddress(this) : {env.recipient}\nmsg.value : {env.value}\nIs deploying contract : {env.contractDeployment}\n")
            debugfile.close()
            debugfile = open(f"raptorevmdebug-{env.tx.txid}.log", "a")
        if not len(env.code):
            return
        while True and (not env.halt):
            try:
                if self.debug:
                    op = env.code[env.pc]
                    history.append(hex(op))
                    self.opcodes[op](env)
                    debugfile.write(f"Program Counter : {env.pc} - last opcode : {hex(op)} - stack : {env.stack} - lastRetValue : {env.lastCallReturn} - memory : {bytes(env.memory.data)} - storage : {env.storage} - remainingGas : {env.remainingGas()} - success : {env.getSuccess()} - halted : {env.halt}\n")
                else:
                    self.opcodes[env.code[env.pc]](env)
            except Exception as e:
                self.log(f"Program Counter : {env.pc}\nStack : {env.stack}\nCalldata : {env.data}\nMemory : {bytes(env.memory.data)}\nCode : {env.code}\nIs deploying contract : {env.contractDeployment}\nHalted : {env.halt}")
                raise

    def deployContract(self, tx):
        self.applyParentStuff(tx)
        deplAddr = w3.toChecksumAddress(w3.keccak(rlp.encode([bytes.fromhex(tx.sender.replace("0x", "")), int(tx.nonce)]))[12:])
        self.ensureExistence(tx.sender)
        self.ensureExistence(deplAddr)
        env = EVM.CallEnv(self.getAccount, tx.sender, self.getAccount(deplAddr), deplAddr, self.beaconChain, tx.value, tx.gasLimit, tx, b"", self.executeChildCall, tx.data, False)
        self.execEVMCall(env)
        self.getAccount(deplAddr).code = env.returnValue
        self.getAccount(deplAddr).storage = env.storage.copy()
        if env.getSuccess():
            self.receipts[tx.txid] = {"transactionHash": tx.txid,"transactionIndex": '0x1',"blockNumber": self.txIndex.get(tx.txid), "blockHash": tx.epoch, "cumulativeGasUsed": hex(env.gasUsed), "gasUsed": hex(env.gasUsed),"contractAddress": (tx.recipient if tx.contractDeployment else None),"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x1'}
            print(f"Deployed contract {deplAddr} in tx {tx.txid}")
        else:
            self.receipts[tx.txid] = {"transactionHash": tx.txid,"transactionIndex": '0x1',"blockNumber": self.txIndex.get(tx.txid), "blockHash": tx.epoch, "cumulativeGasUsed": hex(env.gasUsed), "gasUsed": hex(env.gasUsed),"contractAddress": (tx.recipient if tx.contractDeployment else None),"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x0'}
        for _addr in tx.affectedAccounts:
            self.getAccount(_addr).addParent(tx.txid)


    def tryContractCall(self, tx):
        if tx.contractDeployment:
            env = EVM.CallEnv(self.getAccount, tx.sender, self.getAccount(tx.recipient), tx.recipient, self.beaconChain, tx.value, tx.gasLimit, tx, b"", self.executeChildCall, tx.data, False)
        else:
            env = EVM.CallEnv(self.getAccount, tx.sender, self.getAccount(tx.recipient), tx.recipient, self.beaconChain, tx.value, tx.gasLimit, tx, tx.data, self.executeChildCall, self.getAccount(tx.recipient).code, False)
        if (tx.value > self.getAccount(tx.sender).balance):
            return (False, b"")
        self.ensureExistence(tx.sender)
        self.ensureExistence(tx.recipient)
        senderAcct = self.getAccount(tx.sender)
        recipientAcct = self.getAccount(tx.recipient)
        
        senderAcct.cancelChanges()
        recipientAcct.cancelChanges()
        
        senderAcct.tempBalance -= tx.value
        recipientAcct.tempBalance += tx.value
        if len(env.code):
            self.execEVMCall(env)
            tx.returnValue = env.returnValue
            if env.getSuccess():
                for _addr in tx.affectedAccounts:
                    self.getAccount(_addr).cancelChanges()
                return (True, tx.returnValue.hex())
            else:
                for _addr in tx.affectedAccounts:
                    self.getAccount(_addr).cancelChanges()
                return (False, tx.returnValue.hex())
        else:
            for _addr in tx.affectedAccounts:
                self.getAccount(_addr).cancelChanges()
            return (True, b"")


    def executeContractCall(self, tx, showMessage):
        self.applyParentStuff(tx)
        if (tx.value > self.getAccount(tx.sender).balance):
            self.receipts[tx.txid] = {"transactionHash": tx.txid,"transactionIndex": '0x1',"blockNumber": self.txIndex.get(tx.txid, 0), "blockHash": tx.txid, "cumulativeGasUsed": hex(env.gasUsed), "gasUsed": hex(env.gasUsed),"contractAddress": (tx.recipient if tx.contractDeployment else None),"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x0'}
            return (False, b"")
        self.ensureExistence(tx.sender)
        self.ensureExistence(tx.recipient)
        senderAcct = self.getAccount(tx.sender)
        recipientAcct = self.getAccount(tx.recipient)
        
        senderAcct.cancelChanges()
        recipientAcct.cancelChanges()
        env = EVM.CallEnv(self.getAccount, tx.sender, self.getAccount(tx.recipient), tx.recipient, self.beaconChain, tx.value, tx.gasLimit, tx, tx.data, self.executeChildCall, self.getAccount(tx.recipient).code, False)
        
        senderAcct.tempBalance -= tx.value
        recipientAcct.tempBalance += tx.value
        # if len(env.code):
        self.execEVMCall(env)
        tx.returnValue = env.returnValue
        if showMessage:
            print(f"Success : {env.getSuccess()}\nReturnValue : {env.returnValue}")
        if env.getSuccess():
            self.getAccount(env.recipient).tempStorage = env.storage.copy()
            for _addr in tx.affectedAccounts:
                self.getAccount(_addr).makeChangesPermanent()
                self.getAccount(_addr).addParent(tx.txid)
            tx.messages = tx.messages + env.messages
            self.log(f"Tx messages : {tx.messages}")
            self.receipts[tx.txid] = {"transactionHash": tx.txid,"transactionIndex": '0x1',"blockNumber": self.txIndex.get(tx.txid, 0), "blockHash": tx.txid, "cumulativeGasUsed": hex(env.gasUsed), "gasUsed": hex(env.gasUsed),"contractAddress": (tx.recipient if tx.contractDeployment else None),"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x1'}
            return (True, tx.returnValue.hex())
        else:
            for _addr in tx.affectedAccounts:
                self.getAccount(_addr).cancelChanges()
            self.receipts[tx.txid] = {"transactionHash": tx.txid,"transactionIndex": '0x1',"blockNumber": self.txIndex.get(tx.txid, 0), "blockHash": tx.txid, "cumulativeGasUsed": hex(env.gasUsed), "gasUsed": hex(env.gasUsed),"contractAddress": (tx.recipient if tx.contractDeployment else None),"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x0'}
            return (False, tx.returnValue.hex())
        # else:
            # for _addr in tx.affectedAccounts:
                # self.getAccount(_addr).makeChangesPermanent()
                # self.getAccount(_addr).addParent(tx.txid)
            self.receipts[tx.txid] = {"transactionHash": tx.txid,"transactionIndex": '0x1',"blockNumber": self.txIndex.get(tx.txid, 0), "blockHash": tx.txid, "cumulativeGasUsed": hex(env.gasUsed), "gasUsed": hex(env.gasUsed),"contractAddress": (tx.recipient if tx.contractDeployment else None),"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x1'}
            return (True, b"")
        
        
    def executeChildCall(self, msg):
        if ((msg.value > self.getAccount(msg.msgSender).tempBalance) or ((msg.value > 0) and msg.isStatic)):
            return (False, b"")
        self.ensureExistence(msg.msgSender)
        self.ensureExistence(msg.recipient)
        if (msg.value > 0):
            self.getAccount(msg.msgSender).tempBalance -= msg.value
            self.getAccount(msg.recipient).tempBalance += msg.value
        # code = self.getAccount(msg.recipient).code
        self.execEVMCall(msg)
        # while True and (not msg.halt):
            # try:
                # self.opcodes[msg.code[msg.pc]](msg)
            # except:
                # break
        if (msg.getSuccess() and msg.calltype != 2):
            self.getAccount(msg.recipient).tempStorage = msg.storage.copy()
            if (msg.calltype == 3):
                self.getAccount(msg.recipient).makeChangesPermanent()
                self.getAccount(msg.recipient).code = msg.returnValue
        return (msg.getSuccess(), msg.returnValue)

    def eth_Call(self, call):
        tx = self.CallBlankTransaction(call)
        msg = EVM.Msg(sender=tx.sender, recipient=tx.recipient, value=tx.value, gas=tx.gasLimit, data=tx.data, tx=tx, calltype=0, shallSaveData=False)
        # if tx.contractDeployment:
            # env = EVM.CallEnv(self.getAccount, tx.sender, self.getAccount(tx.recipient), tx.recipient, self.beaconChain, tx.value, tx.gasLimit, tx, b"", self.executeChildCall, tx.data, False)
        # else:
            # env = EVM.CallEnv(self.getAccount, tx.sender, self.getAccount(tx.recipient), tx.recipient, self.beaconChain, tx.value, tx.gasLimit, tx, tx.data, self.executeChildCall, self.getAccount(tx.recipient).code, False)
            # self.execEVMCall(env)
        env = self.getAccount(msg.recipient, True).call(msg)
        for _addr in tx.affectedAccounts:
            self.getAccount(_addr, True).cancelChanges()
        return env

    def playTransaction(self, tx, showMessage):
        _begin_ = time.time()
        _tx = Transaction(tx)
        feedback = False
        if _tx.txtype == 0:
            # feedback = self.executeTransfer(_tx, showMessage)
            # if (_tx.recipient == self.crossChainAddress):
                # feedback = self.executeTransfer(_tx, showMessage)
            # else:
            feedback = self.executeContractCall(_tx, showMessage)
        elif _tx.txtype == 1:
            feedback = self.mineBlock(_tx)
        elif _tx.txtype == 2:
            # if (_tx.recipient == self.crossChainAddress):
                # feedback = self.executeTransfer(_tx, showMessage)
            # else:
            if _tx.contractDeployment:
                feedback = self.deployContract(_tx)
            else:
                feedback = self.executeContractCall(_tx, showMessage)
        elif _tx.txtype == 3:
            # feedback = self.checkOutDeposit(_tx)
            pass # deprecated
        elif _tx.txtype == 4:
            feedback = self.createMN(_tx)
        elif _tx.txtype == 5:
            feedback = self.destroyMN(_tx)
        elif _tx.txtype == 6:
            self.beaconChain.getLastBeacon().depCheckerTxs.append(_tx.txid)
        elif _tx.txtype == 7:
            self.beaconChain.addRelayerSig(_tx.sender, _tx.epoch, _tx.sig)
        
        if (_tx.bio):
            self.accounts[_tx.sender].bio = _tx.bio.replace("%20", " ")
        # if _tx.message:
            # self.leaveMessage(_from, _to, msg, showMessage)
        self.checkDepositsTillIndex(_tx)
        
        for acct in _tx.affectedAccounts:
            _tx.txtype != 6: # don't count txid of ghost transactions
                self.getAccount(acct).addParent(_tx.txid)
            self.getAccount(acct).calcHash()
        self.postTxMessages(_tx)
        self.calcStateRoot()
        self.updateHolders()
        print(f"Transaction {_tx.txid} completed in {round((time.time()-_begin_)*1000, 3)}ms")
        return feedback

    def getLastUserTx(self, _user):
        user = w3.toChecksumAddress(_user)
        self.ensureExistence(user)
        if (len(self.accounts[user].transactions))>0:
            return self.accounts[user].transactions[len(self.accounts[user].transactions)-1]
        else:
            return self.initTxID
            
    def getLastSentTx(self, _user):
        user = w3.toChecksumAddress(_user)
        self.ensureExistence(user)
        if (len(self.accounts[user].sent))>0:
            return self.accounts[user].sent[len(self.accounts[user].sent)-1]
        else:
            return self.initTxID
            
    def getLastReceivedTx(self, _user):
        user = w3.toChecksumAddress(_user)
        self.ensureExistence(user)
        if (len(self.accounts[user].received))>0:
            return self.accounts[user].received[len(self.accounts[user].received)-1]
        else:
            return None
    
    def JSONSerializable(self):
        accountsJSON = {}
        for addr, acct in self.accounts.items():
            accountsJSON[acct.address] = acct.JSONSerializable()
        beaconChainJSON = self.beaconChain.JSONSerializable()
        return {"accounts": accountsJSON, "beaconChain": beaconChainJSON, "totalSupply": self.totalSupply}

class Node(object):
    class Peer(object):
        class PeerError(Exception):
            pass
        
        def __init__(self, url):
            self.node = url if url[len(url)-1] == "/" else url + "/"
            self.lastBlock = {} # needs to be declared
            self.refresh()
        
        def __str__(self):
            return self.node
            
        def __repr__(self):
            return f"Peer({self.node})"
        
        def sendRequest(self, path):
            return requests.get(f"{self.node}{path}")
        
        def refreshOkayNess(self):
            try:
                self.isOkay = self.sendRequest("/ping").json().get("success")
            except:
                self.isOkay = False
            return self.isOkay
        
        def refresh(self):
            self.refreshOkayNess()
            if not self.isOkay:
                return
            _previousRoot = self.systemRoot()
            self.lastBlock = self.sendRequest("/chain/getlastblock").json().get("result")
            if _previousRoot != self.systemRoot():
                self.changed = True
            else:
                pass
        
        def systemRoot(self):
            return self.lastBlock.get("txsRoot", "0x0000000000000000000000000000000000000000000000000000000000000000")
        
        def getBlockByNumber(self, number):
            try:
                return self.sendRequest(f"/chain/block/{number}").json()
            except:
                raise PeerError("Error loading data from peer")
    
    def __init__(self, config):
        self.transactions = {}
        self.txsOrder = []
        self.mempool = []
        self.listenPort = 6969
        self.sigmanager = SignatureManager()
        self.state = State(config["InitTxID"])
        self.config = config
        self.peers = self.loadBatchOfPeers(config["peers"])
        self.bestBlockChecked = 0
        self.goodPeers = []
        self.checkGuys()
        self.initNode()

    def stringifyBatchOfPeers(self, peers):
        stringified = []
        for peer in peers:
            stringified.append(str(peer))
        return stringified

    def loadBatchOfPeers(self, urls):
        _peers = []
        for url in urls:
            _peers.append(self.Peer(url))
        return _peers

    def canBePlayed(self, tx):
        sigVerified = False
        playableByState = False
        if not (json.loads(tx.get("data")).get("type") in [1,2, 6]):
            sigVerified = self.sigmanager.verifyTransaction(tx)
        else:
            sigVerified = True
        playableByState = self.state.willTransactionSucceed(tx)
        return (sigVerified and playableByState, sigVerified, playableByState)
        

    def addTxToMempool(self, tx):
        if (self.canBePlayed(tx)[1]):
            self.mempool.append(tx)


    def initNode(self):
        try:
            self.loadDB()
            print("Successfully loaded node DB !")
        except:
            print("Error loading DB, starting from zero :/")
        # self.upgradeTxs()
        for txHash in self.txsOrder:
            tx = self.transactions[txHash]
            if self.canBePlayed(tx)[0]:
                self.state.playTransaction(tx, False)
            # self.propagateTransactions([tx])
        self.saveDB()
        # self.syncDB()
        self.syncByBlock()
        self.createRefreshTx()
        self.saveDB()

    def checkTxs(self, txs, shouldPropagate=False):
        # print("Pulling DUCO txs...")
        # txs = requests.get(self.config["endpoint"]).json()["result"]
        # print("Successfully pulled transactions !")
#        print("Saving transactions to DB...")
        _counter = 0
        _toPropagate = []
        for tx in txs:
            playable = self.canBePlayed(tx)
            # print(f"Result of canBePlayed for tx {tx['hash']}: {playable}")
            if (not self.transactions.get(tx["hash"]) and playable[0]):
                self.transactions[tx["hash"]] = tx
                self.txsOrder.append(tx["hash"])
                self.state.playTransaction(tx, True)
                _counter += 1
                if shouldPropagate:
                    _toPropagate.append(tx)
                print(f"Successfully saved transaction {tx['hash']}")
        if (shouldPropagate and (len(_toPropagate))):
            self.propagateTransactions(_toPropagate)
        if _counter > 0:
            print(f"Successfully saved {_counter} transactions !")
        self.saveDB()

    def saveDB(self):
        toSave = json.dumps({"transactions": self.transactions, "txsOrder": self.txsOrder})
        file = open(self.config["dataBaseFile"], "w")
        file.write(toSave)
        file.close()

    def loadDB(self):
#        print(self.config["dataBaseFile"])
        file = open(self.config["dataBaseFile"], "r")
        file.seek(0)
        db = json.load(file)
#        print(db)
        self.transactions = db["transactions"]
        self.txsOrder = db["txsOrder"]
        file.close()
    
    # def backgroundRoutine(self):
        # while True:
            # self.checkTxs()
            # self.saveDB()
            # time.sleep(float(self.config["delay"]))
    
    def upgradeTxs(self):
        for txid in self.txsOrder:
            if type(self.transactions[txid]["data"]) == dict:
                self.transactions[txid]["data"] = json.dumps(self.transactions[txid]["data"]).replace(" ", "")
    
    
    
    
    # REQUESTING DATA FROM PEERS
    def askForMorePeers(self):
        for peer in self.goodPeers:
            try:
                obtainedPeers = requests.get(f"{peer}/net/getOnlinePeers")
                for _peer in obtainedPeers:
                    if not ((peer if peer[len(peer)-1] == "/" else (peer + "/")) in self.stringifyBatchOfPeers(self.peers)):
                        self.peers.append(Peer(peer))
            except:
                pass
    
    def checkGuys(self):
        self.goodPeers = []
        for peer in self.peers:
            peer.refreshOkayNess()
            if peer.isOkay:
                self.goodPeers.append(peer)
        self.askForMorePeers()
        self.goodPeers = []
        for peer in self.peers:
            try:
                if (requests.get(f"{peer}/ping").json()["success"]):
                    self.goodPeers.append(peer)
            except:
                pass
    
    def pullSetOfTxs(self, txids):
        txs = []
        for txid in txids:
            localTx = self.transactions.get(txid)
            if not localTx:
                for peer in self.goodPeers:
                    try:
                        tx = peer.sendRequest(f"/get/transactions/{txid}").json()["result"][0]
                        txs.append(tx)
                        break
                    except Exception as e:
                        print("Exception pulling tx:", txid, e)
            else:
                txs.append(localTx)
        return txs


    def pullChildsOfATx(self, txid):
        vwjnvfeuuqubb = self.state.txChilds.get(txid) or []
        children = vwjnvfeuuqubb.copy()
        for peer in self.goodPeers:
            try:
                _childs = requests.get(f"{peer}/accounts/txChilds/{txid}").json()["result"]
                for child in _childs:
                    if not (child in children):
                        pulledTxData = json.loads(self.pullSetOfTxs([child])[0]["data"])
                        if (pulledTxData["parent"] == txid) or (pulledTxData["type"] == 2):
                            children.append(child)
                break
            except:
                pass
        return children
        
    def pullTxsByBlockNumber(self, blockNumber):
        txs = []
        try:
            txs = self.state.beaconChain.blocks.get(blockNumber).transactions.copy()
        except:
            txs = []
        for peer in self.goodPeers:
            try:
                _txs = requests.get(f"{peer}/chain/block/{blockNumber}").json()["result"]["transactions"]
                for _tx in _txs:
                    if not (_tx in txs):
                        txs.append(_tx)
                break
            except:
                pass
        return txs
    
    def execTxAndRetryWithChilds(self, txid):
#        print(f"Loading tx {txid}")
        tx = self.pullSetOfTxs([txid])
#        print(tx)
        self.checkTxs(tx)
        _childs = self.pullChildsOfATx(txid)
        for txid in _childs:
            self.execTxAndRetryWithChilds(txid)
    
    def syncDB(self):
        self.checkGuys()
        toCheck = self.pullChildsOfATx(self.config["InitTxID"])
        for txid in toCheck:
            _childs = self.execTxAndRetryWithChilds(txid)
    
    def getChainLength(self):
        self.checkGuys()
        length = 0
        for peer in self.goodPeers:
            length = max(requests.get(f"{peer}/chain/length").json()["result"], length)
        return length
    
    def syncByBlock(self):
        self.checkTxs(self.pullSetOfTxs(self.pullTxsByBlockNumber(0)))
        for blockNumber in range(self.bestBlockChecked,self.getChainLength()):
            _toCheck_ = self.pullSetOfTxs(self.pullTxsByBlockNumber(blockNumber))
            print(blockNumber)
            self.checkTxs(_toCheck_)
            self.bestBlockChecked = blockNumber
    
    
    def propagateTransactions(self,txs):
        toPush = []
        for tx in txs:
            txString = json.dumps(tx).replace(" ", "")
            txHex = txString.encode().hex()
            toPush.append(txHex)
        toPush = ",".join(toPush)
        for node in self.goodPeers:
            requests.get(f"{node}/send/rawtransaction/?tx={toPush}")
    
    def networkBackgroundRoutine(self):
        while True:
#            print("Refreshing transactions from other nodes")
            self.createRefreshTx()
            self.checkGuys()
            self.syncByBlock()
            time.sleep(60)

    def txReceipt(self, txid):
        try:
            _txid = txid
            if self.state.type2ToType0Hash.get(txid):
                _txid = self.state.type2ToType0Hash.get(txid)
            print(_txid)
            _tx_ = Transaction(self.transactions.get(_txid))
            _blockHash = _tx_.epoch or self.state.getGenesisEpoch()
            _beacon_ = self.state.beaconChain.blocksByHash.get(_blockHash)
            return self.state.receipts.get(_txid, {"transactionHash": _txid,"transactionIndex":  '0x1',"blockNumber": _beacon_.number, "blockHash": _blockHash, "cumulativeGasUsed": '0x5208', "gasUsed": '0x5208',"contractAddress": None,"logs": [], "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","status": '0x1'})
        except:
            return ""
    
    def ethGetTransactionByHash(self, txid):
        try:
            tx = Transaction(self.transactions[txid])
            return tx.web3Returnable()
            # return {"hash": tx.txid, "nonce": hex(tx.nonce), "blockHash": tx.txid, "transactionIndex": "0x0", "from": tx.sender, "to": (None if tx.contractDeployment else tx.recipient), "value": hex(tx.value), "gasPrice": hex(tx.gasprice), "gas": hex(tx.gasLimit), "input": tx.data, "v": tx.v, "r": tx.r, "s": tx.s}
        except:
            return "0x"

    def createRefreshTx(self):
        _index = self.state.beaconChain.bsc.custodyContract.functions.depositsLength().call()
        if self.state.lastIndex >= _index:
            return
        data = json.dumps({"epoch": self.state.getCurrentEpoch(), "indexToCheck": _index, "type": 6})
        _txid_ = w3.soliditySha3(["string"], [data]).hex()
        self.checkTxs([{"data": data, "hash": _txid_}], True)

    def integrateETHTransaction(self, ethTx):
        data = json.dumps({"rawTx": ethTx, "epoch": self.state.getCurrentEpoch(), "indexToCheck": self.state.beaconChain.bsc.custodyContract.functions.depositsLength().call(), "type": 2})
        _txid_ = w3.soliditySha3(["string"], [data]).hex()
        self.checkTxs([{"data": data, "hash": _txid_}], True)
        return _txid_


# thread = threading.Thread(target=node.backgroundRoutine)
# thread.start()

class Terminal(object):
    def __init__(self, nodeClass):
        self.node = nodeClass
        self.commands = {}
        self.commands["snapshot"] = self.snapshot
        self.commands["balance"] = self.balance
        self.commands["tokenBalance"] = self.tokenBalance
        self.commands["account"] = self.accountInfo
        self.commands["stats"] = self.stats
        self.commands["abibeacon"] = self.abibeacon
    
    
    def _encodeWithSelector(self, functionName, params):
        selector = bytes(w3.keccak(str(functionName).encode()))[0:4]
        argTypes = list(filter(("").__ne__, functionName.replace(")", "").split("(")[1].split(",")))
        encodedParams = eth_abi.encode_abi(argTypes, params)
        return (selector + encodedParams)
        
    def encodeWithSelector(self, keyInput):
        encoded = self._encodeWithSelector(keyInput[1], keyInput[2:])
        print(encoded)
        
    def callContract(self, to, function, params, returnTypes):
        callData = self._encodeWithSelector(function, params)
        rawRetValue = self.node.state.eth_Call({"to": to, "data": callData}).returnValue
        return eth_abi.decode_abi(returnTypes, rawRetValue)

    def skip(self, keyInput):
        pass
    
    def snapshot(self, keyInput):
        file = open(keyInput[1], "w")
        serializable = self.node.state.JSONSerializable()
        serialized = json.dumps(serializable)
        file.write(serialized)
        file.close()
    
    def stats(self, keyInput):
        totalSupply = self.node.state.totalSupply
        holders = len(self.node.state.holders)
        txsNumber = len(self.node.txsOrder)
        lastBlockHash = self.node.state.beaconChain.getLastBeacon().proof
        chainLength = len(self.node.state.beaconChain.blocks)
        print(f"Coin stats\n    Total Supply : {totalSupply}\n    Holders : {holders}\n    Number of transactions : {txsNumber}")
        print(f"Chain stats\n    Chain length : {chainLength}\n    Last block hash : {lastBlockHash}")
        
        
    def abibeacon(self, keyInput):
        _id = keyInput[1]
        try:
            if _id.isnumeric():
                print(self.node.state.beaconChain.blocks[int(_id)].ABIEncodable())
            else:
                print(self.node.state.beaconChain.blockByHash.get(_id).ABIEncodable())
        except Exception as e:
            print(e.__repr__())
    
    def balance(self, keyInput):
        addr = keyInput[1]
        acct = self.node.state.getAccount(addr)
        print(f"Address : {acct.address}\nBalance : {acct.balance/(10**18)}")
    
    def tokenBalance(self, keyInput):
        tokenaddr = self.node.state.formatAddress(keyInput[1])
        addr = self.node.state.formatAddress(keyInput[2])
        balance = self.callContract(tokenaddr, "balanceOf(address)", [addr], ["uint256"])[0]
        symbol = self.callContract(tokenaddr, "symbol()", [], ["string"])[0]
        decimals = self.callContract(tokenaddr, "decimals()", [], ["uint8"])[0]
        print(f"Address : {addr} owns {balance/(10**decimals)} {symbol}")
        
    
    def accountInfo(self, keyInput):
        addr = keyInput[1]
        acct = self.node.state.getAccount(addr)
        print(f"Address : {acct.address}\nBalance : {acct.balance/(10**18)}\nBio : {acct.bio}")
        
    
    def execCommand(self, command):
        keyInput = list(filter(("").__ne__, command.split(" "))) or [""]
        self.commands.get(keyInput[0], self.skip)(keyInput)
    
    def terminalLoop(self):
        while True:
            try:
                cmd = input("RaptorChain Terminal - $ ")
                self.execCommand(cmd)
            except Exception as e:
                print(f"Exception occured executing command: {e.__repr__()}")

if __name__ == "__main__":
    node = Node(config)
    print(node.config)
    thread = threading.Thread(target=node.networkBackgroundRoutine)
    thread.start()






# HTTP INBOUND PARAMS
app = flask.Flask(__name__)
app.config["DEBUG"] = False
CORS(app)


@app.route("/")
def basicInfoHttp():
    return f"RaptorChain testnet node running on port {node.listenPort}"

@app.route("/ping")
def getping():
    return json.dumps({"result": "Pong !", "success": True})

@app.route("/stats")
def getStats():
    _stats_ = {"coin": {"transactions": len(node.txsOrder), "supply": node.state.totalSupply, "holders": len(node.state.holders)}, "chain" : {"length": len(node.state.beaconChain.blocks), "difficulty" : node.state.beaconChain.difficulty, "target": node.state.beaconChain.miningTarget, "lastBlockHash": node.state.beaconChain.getLastBeacon().proof}}
    return flask.jsonify(result=_stats_, success=True)

@app.route("/VMRoot")
def getVMRoot():
    return node.state.beaconChain.getLastBeacon().txsRoot().hex()

# HTTP GENERAL GETTERS - pulled from `Node` class
@app.route("/get/transactions", methods=["GET"]) # get all transactions in node
def getTransactions():
    return flask.jsonify(result=node.transactions, success=True)

@app.route("/get/nFirstTxs/<n>", methods=["GET"]) # GET N first transactions
def nFirstTxs(n):
    _n = min(len(node.txsOrder), int(n))
    txs = []
    for txid in txsOrder[0:int(n)-1]:
        txs.append(node.transactions.get(txid))
    return flask.jsonify(result=txs, success=True)
    
@app.route("/get/nLastTxs/<n>", methods=["GET"]) # GET N last transactions
def nLastTxs(n):
    _n = min(len(node.txsOrder), int(n))
    _n = len(node.txsOrder)-int(_n)
    txs = []
    for txid in node.txsOrder[_n:len(node.txsOrder)]:
        txs.append(node.transactions.get(txid))
        
    return flask.jsonify(result=txs, success=True)

@app.route("/get/txsByBounds/<upperBound>/<lowerBound>", methods=["GET"]) # get txs from upperBound to lowerBound (in index)
def getTxsByBound(upperBound, lowerBound):
    upperBound = min(upperBound, len(node.txsOrder)-1)
    lowerBound = max(lowerBound, 0)
    for txid in node.txsOrder[lowerBound:upperBound]:
        txs.append(node.transactions.get(txid))
    return flask.jsonify(result=txs, success=True)

@app.route("/get/txIndex/<index>")
def getTxIndex(txid):
    _index = node.state.txIndex.get(tx)
    if _index != None:
        return flask.jsonify(result=_index, success=True)
    else:
        return (flask.jsonify(message="TX_NOT_FOUND", success=False), 404)

@app.route("/get/transaction/<txhash>", methods=["GET"]) # get specific tx by hash
def getTransactionByHash(txhash):
    tx = node.transactions.get(txhash)
    if (tx != None):
        return flask.jsonify(result=tx, success=True)
    else:
        return (flask.jsonify(message="TX_NOT_FOUND", success=False), 404)

@app.route("/get/transactions/<txhashes>", methods=["GET"]) # get specific tx by hash
def getMultipleTransactionsByHashes(txhashes):
    txs = []
    oneSucceeded = False
    _txhashes = txhashes.split(",")
    for txhash in _txhashes:
        tx = node.transactions.get(txhash)
        if (tx):
            txs.append(tx)
            oneSucceeded = True
    return flask.jsonify(result=txs, success=oneSucceeded)

@app.route("/get/numberOfReferencedTxs") # get number of referenced transactions
def numberOfTxs():
    return flask.jsonify(result=len(node.txsOrder), success=True)



# ACCOUNT-BASED GETTERS (obtained from `State` class)
@app.route("/accounts/accountInfo/<account>") # Get account info (balance and transaction hashes)
def accountInfo(account):
    _address = w3.toChecksumAddress(account)
    acct = node.state.getAccount(_address, True)
    balance = acct.balance
    transactions = acct.transactions
    try:
        bio = acct.bio
    except:
        bio = ""
    code = acct.code.hex()
    storage = acct.storage
    nonce = len(acct.sent)
    return flask.jsonify(result={"balance": (balance or 0), "tempBalance": acct.tempBalance, "nonce": nonce, "transactions": transactions, "bio": bio, "code": code, "storage": storage}, success= True)

@app.route("/accounts/sent/<account>")
def sentByAccount(account):
    _address = w3.toChecksumAddress(account)    
    return flask.jsonify(result=node.state.getAccount(_address, True).sent, success=True)

@app.route("/accounts/accountBalance/<account>")
def accountBalance(account):
    _address = w3.toChecksumAddress(account)
    balance = 0
    try:
        balance = node.state.accounts.get(_address).balance
    except:
        balance = 0
    return flask.jsonify(result={"balance": (balance or 0)}, success=True)

@app.route("/accounts/txChilds/<tx>")
def txParent(tx):
    _kids = node.state.txChilds.get(tx)
    if _kids != None:
        return flask.jsonify(result=_kids, success=True)
    else:
        return flask.jsonify(message="TX_NOT_FOUND", success=False)

# SEND TRANSACTION STUFF (redirected to `Node` class)
@app.route("/send/rawtransaction/") # allows sending a raw (signed) transaction
def sendRawTransactions():
    rawtxs = str(flask.request.args.get('tx', None))
    rawtxs = rawtxs.split(",")
    txs = []
    hashes = []
    for rawtx in rawtxs:
        tx = json.loads(bytes.fromhex(rawtx).decode())
        print(tx)
        if (type(tx["data"]) == dict):
            tx["data"] = json.dumps(tx["data"]).replace(" ", "")
        if not tx.get("indexToCheck", None):
            tx["indexToCheck"] = node.state.beaconChain.bsc.custodyContract.functions.depositsLength().call()
        txs.append(tx)
        hashes.append(tx["hash"])
    node.checkTxs(txs, True)
    return flask.jsonify(result=hashes, success=True)

@app.route("/send/buildtransaction/")
def buildTransactionAndSend():
    privkey = str(flask.request.args.get('privkey', None))
    _from = str(flask.request.args.get('from', None))
    _to = str(flask.request.args.get('to', None))
    tokens = str(flask.request.args.get('value', None))
    result = buildTransaction(self, privkey, _from, _to, tokens)[0]
    return flask.jsonify(result=result[0], success=result[1])


# BEACON RELATED DATA (loaded from node/state/beaconChain)
@app.route("/chain/block/<block>")
def getBlock(block):
    _block = node.state.beaconChain.getBlockByHeightJSON(int(block))
    return flask.jsonify(result=_block, success=not not _block)

@app.route("/chain/blockByHash/<blockhash>")
def blockByHash(blockhash):
    _block = node.state.beaconChain.blocksByHash.get(blockhash)
    if _block:
        _block = _block.exportJson()
    return flask.jsonify(result=_block, success=not not _block)

@app.route("/chain/getlastblock")
def getlastblock():
    return flask.jsonify(result=node.state.beaconChain.getLastBlockJSON(), success=True)    

@app.route("/chain/miningInfo")
def getMiningInfo():
    _result = {"difficulty" : node.state.beaconChain.difficulty, "target": node.state.beaconChain.miningTarget, "lastBlockHash": node.state.beaconChain.getLastBeacon().proof}
    return flask.jsonify(result=_result, success=True)

@app.route("/chain/length")
def getChainLength():
    return flask.jsonify(result=len(node.state.beaconChain.blocks), success=True)

@app.route("/chain/mempool")
def getMempool():
    return flask.jsonify(result=node.state.beaconChain.exportMempool(), success=True)

# SHARE PEERS (from `Node` class)
@app.route("/net/getPeers")
def shareMyPeers():
    return flask.jsonify(result=node.stringifyBatchOfPeers(node.peers), success=True)
    
@app.route("/net/getOnlinePeers")
def shareOnlinePeers():
    return flask.jsonify(result=node.stringifyBatchOfPeers(node.goodPeers), success=True)



# WEB3 COMPATIBLE RPC
@app.route("/web3", methods=["POST"])
def handleWeb3Request():
    _begin = time.time()
    data = flask.request.get_json()
    print(f"/web3 POST received, data : {data}")
    _id = data.get("id")
    method = data.get("method")
    params = data.get("params")
    result = hex(node.state.chainID)
    if method == "eth_getBalance":
        result = hex(int((node.state.getAccount(w3.toChecksumAddress(params[0]),True).balance)))
    if method == "net_version":
        result = str(node.state.chainID)
    if method == "eth_coinbase":
        result = node.state.beaconChain.getLastBeacon().miner
    if method == "eth_mining":
        result = False
    if method == "eth_gasPrice":
        result = "0x1"
    if method == "eth_blockNumber":
        # result = hex(len(node.state.beaconChain.blocks) - 1)
        result = hex(len(node.transactions) - 1)
    if method == "eth_getTransactionCount":
        result = hex(len(node.state.getAccount(w3.toChecksumAddress(params[0]), True).sent))
    if method == "eth_getCode":
        result = "0x"
    if method == "eth_estimateGas":
        result = hex(node.state.eth_Call(params[0]).gasUsed)
    # if method == "eth_sign":
        # result = w3.eth.account.sign_message(encode_defunct(text=), private_key="").signature.hex()
    if method == "eth_call":
        result = f"0x{node.state.eth_Call(params[0]).returnValue.hex()}"
    if method == "eth_getCompilers":
        result = []
    if method == "eth_sendRawTransaction":
        result = node.integrateETHTransaction(params[0])
    if method == "eth_getTransactionReceipt":
        result = node.txReceipt(params[0])
    if method == "eth_getCode":
        result = f"0x{node.state.getAccount(params[0], True).code.hex()}"
    if method == "eth_getStorageAt":
        result = hex(int(node.state.getAccount(params[0], True).storage[int(params[1])]))
    if method == "eth_getTransactionByHash":
        result = node.ethGetTransactionByHash(params[0])
    _respdict = {"id": _id, "jsonrpc": "2.0", "result": result}
    print(f"{data.get('method')} request completed in {round((time.time() - _begin)*1000, 3)}ms")
    return flask.Response(json.dumps(_respdict), mimetype='application/json');
    
def runFlask():
    app.run(host="0.0.0.0", port=node.listenPort, ssl_context=ssl_context)

if __name__ == "__main__":
    print(ssl_context or "No SSL context defined")
    _thread = threading.Thread(target=runFlask)
    _thread.start()
    Terminal(node).terminalLoop()
