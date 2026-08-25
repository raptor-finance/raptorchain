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
