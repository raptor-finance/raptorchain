"""Core datatypes for RaptorChain.

Extracted from RaptorChain.py (originally the Message and Transaction
classes).  Living in their own module breaks the circular import between
RaptorChain.py and web3rpc.py: both can import these types at module level.

Dependencies are intentionally limited to modules that never import
RaptorChain (constants, utils, crypto.eth_decoder).
"""

import json

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
            self.gasprice = ethDecoded.gas_price
            self.gasLimit = ethDecoded.gas
            self.fee = ethDecoded.gas_price*self.gasLimit
            self.sender = ethDecoded.from_
            self.recipient = ethDecoded.to
            self.value = int(ethDecoded.value)
            self.nonce = ethDecoded.nonce
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
        self.indexToCheck = txData.get("indexToCheck", 0)
        
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
