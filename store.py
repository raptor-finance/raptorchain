import json
import os
import tempfile
import threading


class Store(object):
    """Persistence layer for the node's chain data.

    Owns everything related to where/how chain data is stored on disk,
    so the storage backend can be swapped without touching Node logic.
    """

    def __init__(self, path):
        self.path = path
        self.transactions = {}
        self.txsOrder = []
        self._lock = threading.Lock()

    def load(self):
        """Load the database from disk into memory. Raises on failure."""
        with self._lock:
            with open(self.path, "r") as file:
                db = json.load(file)
            self.transactions = db["transactions"]
            self.txsOrder = db["txsOrder"]

    def addTransaction(self, tx):
        """Atomically insert a transaction and record its order.

        Keeps the transactions dict and txsOrder list consistent under a
        single lock acquisition. Returns True if the transaction was new,
        False if it was already stored.
        """
        txHash = tx["hash"]
        with self._lock:
            if self.transactions.get(txHash):
                return False
            self.transactions[txHash] = tx
            self.txsOrder.append(txHash)
            return True

    def hasTransaction(self, txHash):
        """Return True if a transaction with this hash is stored."""
        with self._lock:
            return bool(self.transactions.get(txHash))

    def getTransaction(self, txid, hashMap=None):
        """Look up a transaction by hash.

        Optionally resolves txid through hashMap first (e.g. the type-2 to
        type-0 hash mapping maintained by the state).
        """
        _txid = hashMap.get(txid, txid) if hashMap else txid
        with self._lock:
            return self.transactions.get(_txid)

    def getTxHashes(self):
        """Return a snapshot copy of the ordered transaction hash list."""
        with self._lock:
            return list(self.txsOrder)

    def getAllTransactions(self):
        """Return a snapshot copy of all stored transactions."""
        with self._lock:
            return dict(self.transactions)

    def getNTxs(self, n, newestFirst=False):
        """Return the n first (or n last) transactions, in stored order."""
        with self._lock:
            count = min(len(self.txsOrder), int(n))
            if newestFirst:
                hashes = self.txsOrder[len(self.txsOrder)-count:]
            else:
                hashes = self.txsOrder[:count]
            return [self.transactions.get(hash) for hash in hashes]

    def getTxsByRange(self, start, end):
        """Return transactions whose order index falls in [start:end)."""
        with self._lock:
            return [self.transactions.get(hash) for hash in self.txsOrder[start:end]]

    def txCount(self):
        """Return the number of stored transactions."""
        with self._lock:
            return len(self.txsOrder)

    def normalizeTxData(self):
        """Rewrite transaction payloads stored as dicts to compact JSON strings."""
        with self._lock:
            for txid in self.txsOrder:
                tx = self.transactions.get(txid)
                if tx and type(tx["data"]) == dict:
                    tx["data"] = json.dumps(tx["data"]).replace(" ", "")

    def save(self):
        """Atomically and durably persist the full database to disk.

        Writes to a unique temporary file in the same directory, fsyncs it,
        then atomically renames it over the target. The parent directory is
        fsynced afterwards so the rename itself survives a crash/power loss.
        A lock serializes concurrent saves (HTTP handlers + background
        routine) so tmp files can never interleave.
        """
        with self._lock:
            toSave = json.dumps({"transactions": self.transactions, "txsOrder": self.txsOrder})
            dirPath = os.path.dirname(os.path.abspath(self.path))
            fd, tmpPath = tempfile.mkstemp(prefix=os.path.basename(self.path) + ".", suffix=".tmp", dir=dirPath)
            try:
                with os.fdopen(fd, "w") as file:
                    file.write(toSave)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(tmpPath, self.path)
            except BaseException:
                # never leave a half-written tmp file behind on failure
                try:
                    os.unlink(tmpPath)
                except OSError:
                    pass
                raise
            # fsync the directory so the rename is durable too
            try:
                dirFd = os.open(dirPath, os.O_RDONLY)
                try:
                    os.fsync(dirFd)
                finally:
                    os.close(dirFd)
            except OSError:
                pass  # best-effort: not all filesystems support directory fsync
