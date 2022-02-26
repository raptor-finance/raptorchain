class Client:
    def __init__(self, NodeAddr):
        # self.chain = BeaconChain()
        import importlib
        import hashlib
        self.requests = importlib.import_module("requests")
        
        from eth_account.account import Account
        
        from myCrypto_client import BeaconChain, Beacon, GenesisBeacon, SignatureManager        
        self.node = NodeAddr
        self.signer = SignatureManager()
        self.difficulty = 1
        self.target = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        self.lastBlock = ""
        self.priv_key = hashlib.sha256(b"SiriCoin Will go to MOON - Just a disposable key").hexdigest()
        self.address = Account().from_key(self.priv_key).address
        _txs = self.requests.get(f"{self.node}/accounts/accountInfo/{self.address}").json().get("result").get("transactions")
        self.lastSentTx = _txs[len(_txs)-1]
        self.refresh()
    
    def refresh(self):
        info = self.requests.get(f"{self.node}/chain/miningInfo").json().get("result")
        self.target = info["target"]
        self.difficulty = info["difficulty"]
        self.lastBlock = info["lastBlockHash"]
        _txs = self.requests.get(f"{self.node}/accounts/accountInfo/{self.address}").json().get("result").get("transactions")
        self.lastSentTx = _txs[len(_txs)-1]
    
    def submitBlock(self, blockData):
        self.refresh()
        data = json.dumps({"from": self.address, "to": self.address, "tokens": 0, "parent": self.lastSentTx, "blockData": blockData, "epoch": self.lastBlock, "type": 1})
        tx = {"data": data}
        tx = signer.signTransaction(self.priv_key, tx)
#        print(tx)
        return self.requests.get(f"{self.node}/send/rawtransaction/?tx={json.dumps(tx).encode().hex()}").json().get("result")[0]
