"""Core datatypes for RaptorChain.

Extracted from RaptorChain.py (originally the Message and Transaction
classes).  Living in their own module breaks the circular import between
RaptorChain.py and web3rpc.py: both can import these types at module level.

Dependencies are intentionally limited to modules that never import
RaptorChain (constants, utils, crypto.eth_decoder).
"""

import json

import eth_abi
import rlp
from web3.auto import w3

from . import constants
from .utils import formatAddress
from crypto.eth_decoder import ETHTransactionDecoder


class Message(object):
    def __init__(self, _from, _to, msg):
        self.sender = _from
        self.recipient = _to
        self.msg = msg

class Transaction(object):
    def __init__(self, tx):
        self.persist = True
        self.notTry = True
        txData = json.loads(tx["data"])
        self.contractDeployment = False
        self.txtype = (txData.get("type") or 0)
        self.messages = []
        self.systemMessages = []
        self.affectedAccounts = []
        self.accountsToDestroy = []
        
        # variable to be edited later
        self.nonMalleable = True
        
        # to be edited during execution
        self.events = []
        self.logsBloom = bytearray(256)
        
        # to be edited later
        self.nonce = 0
        self.gasprice = 0
        self.gasUsed = 0
        
        # tx timestamps will be used later
        self.timestamp = txData.get("timestamp")
        
        self.epoch = txData.get("epoch")
        _sig = tx.get("sig")
        self.sig = bytes.fromhex(_sig.replace("0x", "")) if _sig else b""
        if _sig:
            (self.v, self.r, self.s) = (self.sig[64], self.sig[0:32], self.sig[32:64])
        if (self.txtype == 0): # legacy transfer
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.recipient = w3.toChecksumAddress(txData.get("to"))
            self.value = max(int(txData.get("tokens")), 0)
            self.affectedAccounts = [self.sender, self.recipient]
            self.gasprice = constants.DEFAULT_GAS_PRICE
            self.gasLimit = constants.DEFAULT_GAS_LIMIT
            self.fee = self.gasprice*self.gasLimit
            try:
                self.data = bytes.fromhex(txData.get("callData", "").replace("0x", ""))
            except:
                self.data = b""
        if (self.txtype == 1): # block mining/staking tx
            self.fee = 0
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.blockData = txData.get("blockData")
            self.recipient = constants.ZERO_ADDRESS
            self.value = 0
            self.affectedAccounts = [self.sender]
            self.gasprice = 0
        elif self.txtype == 2: # metamask transaction
            decoder = ETHTransactionDecoder()
            ethDecoded = decoder.decode_raw_tx(txData.get("rawTx"))
            self.gasprice = int(ethDecoded.gas_price or 0)
            self.gasLimit = int(ethDecoded.gas or 0)
            self.fee = self.gasprice * self.gasLimit
            self.sender = ethDecoded.from_
            self.recipient = ethDecoded.to
            self.value = int(ethDecoded.value or 0)
            self.nonce = int(ethDecoded.nonce or 0)
            self.ethData = ethDecoded.data
            self.ethTxid = ethDecoded.hash_tx
            self.chainId = ethDecoded.chain_id
            self.v = ethDecoded.v
            self.r = ethDecoded.r
            self.s = ethDecoded.s
            
            self.nonMalleable = (int(self.s, 16) <= 0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0)
            
            self.data = bytes.fromhex(ethDecoded.data.replace("0x", ""))
            if not self.recipient:
                self.recipient = w3.toChecksumAddress(w3.keccak(rlp.encode([bytes.fromhex(self.sender.replace("0x", "")), int(self.nonce)]))[12:])
                self.contractDeployment = True
        elif self.txtype == 3: # deposits checking trigger
            self.fee = 0
            self.l2hash = txData["l2hash"]
            self.value = 0
            self.sender = w3.toChecksumAddress(txData.get("from"))
            self.recipient = constants.ZERO_ADDRESS
            self.affectedAccounts = [self.sender]
        elif self.txtype == 4: # MN create
            self.fee = 0
            self.value = constants.MN_COLLATERAL
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
            self.sender = constants.ZERO_ADDRESS
            self.recipient = constants.ZERO_ADDRESS
            self.value = 0
        elif self.txtype == 7: # relayer sign block
            self.fee = 0
            self.sender = txData.get("from")
            self.recipient = constants.ZERO_ADDRESS
            self.blocksig = txData.get("blocksig")
            self.blockhash = txData.get("blockhash", self.epoch)
            self.value = 0
        
        self.bio = txData.get("bio")
        self.parent = txData.get("parent")
        self.message = txData.get("message")
        self.txid = w3.solidityKeccak(["string"], [tx["data"]]).hex()
        self.indexToCheck = int(txData.get("indexToCheck", 0) or 0)
        
        # self.PoW = ""
        # self.endTimeStamp = 0
        
    def formatAddress(self, _addr):
        return formatAddress(_addr)
        
    def markAccountAffected(self, addr):
        _addr = self.formatAddress(addr)
        if not _addr in self.affectedAccounts:
            self.affectedAccounts.append(_addr)

    def addToBloom(self, _data):
        _hash = w3.keccak(_data)
        for idx in [0, 2, 4]:
            bitToSet = (int.from_bytes(_hash[idx:idx+2], "big") & 0x07ff)
            bit_index = 0x07ff - bitToSet
            byte_index = bit_index // 8
            bit_value = 1 << (7 - (bit_index % 8))
            self.logsBloom[byte_index] = self.logsBloom[byte_index] | bit_value

    def addEventToBloom(self, _event):
        for _bloomable in _event.bloomableData:
            self.addToBloom(_bloomable)

    def setEvents(self, _events):
        n = 0
        for e in _events:
            e.setIndex(n)
            self.addEventToBloom(e)
            self.events.append(e.JSONEncodable())
            n+=1

    def web3Returnable(self, _txIndex=0):
        return {
                "hash": self.txid,
                "blockHash": self.epoch,
                "nonce": hex(self.nonce),
                # could be anything due to semi-asynchronous nature
                "transactionIndex": hex(_txIndex),
                "from": self.sender,
                "to": (None if self.contractDeployment else self.recipient),
                "value": hex(self.value),
                "gasPrice": hex(self.gasprice),
                "gas": hex(self.gasLimit),
                "input": self.data.hex(),
                "v": self.v,
                "r": self.r.hex() if type(self.r) == bytes else self.r,
                "s": self.s.hex() if type(self.s) == bytes else self.s
            }


# --- Beacon chain datatypes --------------------------------------------------
# Moved from RaptorChain.py (were nested inside BeaconChain).  Pure data +
# computation: hashing, signatures, ABI encoding, serialization.  No I/O.

class Masternode(object):
    def __init__(self, owner, operator, collateral=constants.MN_COLLATERAL):
        self.owner = w3.toChecksumAddress(owner)
        self.operator = w3.toChecksumAddress(operator)
        self.collateral = collateral
        self.hash = w3.solidityKeccak(["address", "address", "uint256"], [self.owner, self.operator, int(self.collateral)])
        self.blocks = []
    
    def updateHash(self):
        self.hash = w3.solidityKeccak(["address", "address", "uint256"], [self.owner, self.operator, int(self.collateral)])

    def JSONSerializable(self):
        return {"owner": self.owner, "operator": self.operator, "collateral": self.collateral, "blocks": self.blocks, "hash": self.hash.hex()}

class BeaconBase(object):
    logsBloom = bytearray(256)
    totalDifficulty = 0

    def addTransaction(self, txid):
        if not txid in self.transactions:
            self.transactions.append(txid)
        if not txid in self.fullTxList:
            self.fullTxList.append(txid)

    def addToBloom(self, _data):
        _hash = w3.keccak(_data)
        for idx in [0, 2, 4]:
            bitToSet = (int.from_bytes(_hash[idx:idx+2], "big") & 0x07ff)
            bit_index = 0x07ff - bitToSet
            byte_index = bit_index // 8
            bit_value = 1 << (7 - (bit_index % 8))
            self.logsBloom[byte_index] = self.logsBloom[byte_index] | bit_value

    def addEventToBloom(self, _event):
        for b in _event.bloomableData:
            self.addToBloom(b)
            
    def setEvents(self, _events):
        for _event in _events:
            self.addEventToBloom(_event)
            
    def web3Returnable(self):
        return {'difficulty': hex(self.difficulty),
            'extraData': '0x',
            # gas limit not limited by beacon blocks, thus returning highest possible number
            'gasLimit': '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
            # since gas used isn't consumed INSIDE block, returns 0 (could be updated to return a value in the future)
            'gasUsed': '0x0',
            'hash': ("0x" + self.proof) if not self.proof.startswith("0x") else self.proof,
            'logsBloom': "0x" + self.logsBloom.hex(),
            'miner': self.miner,
            'mixHash': ("0x" + self.beaconRoot()) if not self.beaconRoot().startswith("0x") else self.beaconRoot(),
            'nonce': hex(self.nonce),
            'number': hex(self.number),
            'parentHash': self.parent.hex() if type(self.parent) == bytes else self.parent,
            # compatibility
            'stateRoot': "0x" + self.txsRoot().hex(),
            'receiptsRoot': "0x" + self.txsRoot().hex(),
            'transactionsRoot': "0x" + self.txsRoot().hex(),
            
            'sha3Uncles': '0x0000000000000000000000000000000000000000000000000000000000000000',
            'size': '0x0',
            'timestamp': hex(self.timestamp),
            'totalDifficulty': hex(self.totalDifficulty),
            'transactions': self.transactions,
            'uncles': []
        }

class GenesisBeacon(BeaconBase):
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
            self.timestamp = 1658340032
            self.miner = "0x0000000000000000000000000000000000000000"
            self.parent = b"Say hello to RaptorChain Mainnet"
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
        self.fullTxList = []
        self.son = ""
        self.number = 0
        self.nextBlockTx = None
        self.v = 0
        self.r = "0x0000000000000000000000000000000000000000000000000000000000000000"
        self.s = "0x0000000000000000000000000000000000000000000000000000000000000000"
        self.sig = "0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        self.relayerSigs = {}
        
    def beaconRoot(self):
        messagesHash = w3.keccak(eth_abi.encode_abi(["bytes[]"], [self.decodedMessages]))
        bRoot = w3.solidityKeccak(["bytes32", "uint256", "bytes","address"], [self.parent, self.timestamp, messagesHash, self.miner]) # parent PoW hash (bytes32), beacon's timestamp (uint256), beacon miner (address)
        return bRoot.hex()

    def proofOfWork(self):
        bRoot = self.beaconRoot()
        proof = w3.solidityKeccak(["bytes32", "uint256"], [bRoot, int(self.nonce)])
        return proof.hex()

    def messagesToHex(self):
        _msgs = []
        for _msg_ in self.decodedMessages:
            _msgs.append(f"0x{_msg_.hex()}")
        return _msgs

    def addDepCheckerTx(self, txid):
        self.depCheckerTxs.append(txid)
        self.fullTxList.append(txid)


    def difficultyMatched(self):
        return int(self.proofOfWork(), 16) < self.miningTarget

    def ABIEncodable(self):
        return ([self.miner, int(self.nonce),[f"0x{m.hex()}" for m in self.decodedMessages],int(self.difficulty), self.miningTarget, int(self.timestamp), ("0x" + ((self.parent + (b'\x00' * (32-len(self.parent)))).hex())), self.proof, int(self.number), "0x0000000000000000000000000000000000000000000000000000000000000000", self.parentTxRoot, int(self.v), "0x" + self.r.to_bytes(32, "big").hex(), "0x" + self.s.to_bytes(32, "big").hex(), [f"{s}" for r, s in self.relayerSigs.items()]])

    # def exportJson(self):
        # return {"transactions": self.transactions, "messages": self.messages.hex(), "parent": self.parent.hex(), "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}}

    def txsRoot(self):
        return w3.solidityKeccak(["bytes32", "bytes32[]"], [self.proof, sorted(self.transactions)])

    def exportJson(self):
        return {"transactions": (self.fullTxList + [self.nextBlockTx]), "txsRoot": self.txsRoot().hex(), "messages": self.messages.hex(), "decodedMessages": self.messagesToHex(), "parentTxRoot": self.parentTxRoot, "parent": self.parent.hex(), "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}, "signature": {"v": self.v, "r": self.r, "s": self.s, "sig": self.sig}, "relayerSigs": [f"{s}" for r, s in self.relayerSigs.items()]}


class Beacon(BeaconBase):
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
        self.fullTxList = []
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
        self.relayerSigs = {}
    

    def beaconRoot(self):
        messagesHash = w3.solidityKeccak(["bytes"], [self.messages])
        bRoot = w3.solidityKeccak(["bytes32", "uint256", "bytes32", "bytes32","address"], [self.parent, int(self.timestamp), messagesHash, self.parentTxRoot, self.miner]) # parent PoW hash (bytes32), beacon's timestamp (uint256), hash of messages (bytes32), beacon miner (address)
        return bRoot.hex()

    def proofOfWork(self):
        bRoot = self.beaconRoot()
#        print(f"Beacon root : {bRoot}")
        proof = w3.solidityKeccak(["bytes32", "uint256"], [bRoot, int(self.nonce)])
        return proof.hex()

    def difficultyMatched(self):
        return int(self.proofOfWork(), 16) < int(self.miningTarget, 16)

    def signatureMatched(self):
        return (w3.eth.account.recoverHash(self.proof, vrs=(self.v, self.r, self.s)) == self.miner)

    def canAddSig(self, sig):
        _bytesSig = bytes.fromhex(sig.replace("0x", "")) if (type(sig) == str) else sig
        if (len(_bytesSig) != 65):
            return (False, "INVALID_SIG")
        signer = w3.eth.account.recoverHash(self.proof, signature=sig)
        if self.relayerSigs.get(signer):
            return (False, "SIG_ALREADY_EXISTS")
        return (True, signer)
        

    def submitRelayerSig(self, sig):
        _isokay = self.canAddSig(sig)
        if _isokay[0]:
            self.relayerSigs[_isokay[1]] = sig
        return _isokay

    def messagesToHex(self):
        _msgs = []
        for _msg_ in self.decodedMessages:
            _msgs.append(f"0x{_msg_.hex()}")
        return _msgs
        
    def addDepCheckerTx(self, txid):
        self.depCheckerTxs.append(txid)
        self.fullTxList.append(txid)

    def txsRoot(self):
        return w3.solidityKeccak(["bytes32", "bytes32[]"], [self.proof, sorted(self.transactions)])

    def ABIEncodable(self):
        return ([self.miner, int(self.nonce),[f"0x{m.hex()}" for m in self.decodedMessages],int(self.difficulty), self.miningTarget, int(self.timestamp), self.parent, self.proof, int(self.number), "0x0000000000000000000000000000000000000000000000000000000000000000", self.parentTxRoot, int(self.v), "0x" + self.r.to_bytes(32, "big").hex(), "0x" + self.s.to_bytes(32, "big").hex(), [f"{s}" for r, s in self.relayerSigs.items()]])

    def exportJson(self):
        # return {"transactions": self.transactions, "messages": self.messages.hex(), "decodedMessages": self.messagesToHex(), "parent": self.parent, "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}, "signature": {"v": self.v, "r": self.r, "s": self.s, "sig": self.sig}, "ABIEncodableTuple": self.ABIEncodableTuple()}
        return {"transactions": (self.fullTxList + [self.nextBlockTx]), "txsRoot": self.txsRoot().hex(),"messages": self.messages.hex(), "parentTxRoot": self.parentTxRoot, "decodedMessages": self.messagesToHex(), "parent": self.parent, "son": self.son, "timestamp": self.timestamp, "height": self.number, "miningData": {"miner": self.miner, "nonce": self.nonce, "difficulty": self.difficulty, "miningTarget": self.miningTarget, "proof": self.proof}, "signature": {"v": self.v, "r": self.r, "s": self.s, "sig": self.sig}, "relayerSigs": [f"{s}" for r, s in self.relayerSigs.items()]}

