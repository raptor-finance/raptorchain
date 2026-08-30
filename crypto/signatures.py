"""Transaction signature management.

Extracted from RaptorChain.py (originally the SignatureManager class).
Responsible for signing and verifying RaptorChain-native transactions
(txtype 0, 1, 3-7) using secp256k1 over a keccak256 hash of the tx data.
"""

import json

from web3.auto import w3
from eth_account import Account
from eth_account.messages import encode_defunct


class SignatureManager(object):
    def __init__(self):
        self.verified = 0
        self.signed = 0

    def signTransaction(self, private_key, transaction):
        message = encode_defunct(text=transaction["data"])
        transaction["hash"] = w3.solidity_keccak(["string"], [transaction["data"]]).hex()
        _signature = Account.sign_message(message, private_key=private_key).signature.hex()
        signer = Account.recover_message(message, signature=_signature)
        sender = w3.to_checksum_address(json.loads(transaction["data"])["from"])
        if (signer == sender):
            transaction["sig"] = _signature
            self.signed += 1
        return transaction

    def verifyTransaction(self, transaction):
        message = encode_defunct(text=transaction["data"])
        _hash = w3.solidity_keccak(["string"], [transaction["data"]]).hex()
        _hashInTransaction = transaction["hash"]
        signer = Account.recover_message(message, signature=transaction["sig"])
        sender = w3.to_checksum_address(json.loads(transaction["data"])["from"])
        result = ((signer == sender) and (_hash == _hashInTransaction))
        self.verified += int(result)
        return result
