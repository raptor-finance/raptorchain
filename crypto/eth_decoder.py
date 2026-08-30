"""Ethereum-style raw transaction decoder.

Extracted from RaptorChain.py (originally the ETHTransactionDecoder class).
Used to decode MetaMask / EVM-compatible raw transactions (txtype 2) so
they can be replayed on the RaptorChain VM.
"""

from dataclasses import dataclass
from typing import Optional

import rlp
from web3.auto import w3
from eth_account import Account
from eth_utils import keccak
from rlp.sedes import Binary, big_endian_int, binary


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
        hash_tx = w3.to_hex(keccak(bytesTx))
        from_ = Account.recover_transaction(raw_tx)
        to = w3.to_checksum_address(tx.to) if tx.to else None
        data = w3.to_hex(tx.data)
        r = hex(tx.r)
        s = hex(tx.s)
        chain_id = (tx.v - 35) // 2 if tx.v % 2 else (tx.v - 36) // 2
        return self.DecodedTx(hash_tx, from_, to, tx.nonce, tx.gas, tx.gas_price, tx.value, data, chain_id, r, s, tx.v)
