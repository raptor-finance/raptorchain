import json
import os
import shutil
import tempfile
import threading


class Store(object):
    """Persistence layer for the node's chain data.

    Owns everything related to where/how chain data is stored on disk,
    so the storage backend can be swapped without touching Node logic.

    On-disk layout: a directory containing two line-oriented text files:
      - "transactions": one compact JSON transaction per line (order irrelevant)
      - "txsOrder":     one transaction hash per line, in stored order

    Saves are O(new transactions): new txs are appended to "transactions",
    then their hashes to "txsOrder" (in that order, each fsynced). A crash
    between the two appends can only orphan a tx (never dangle an order
    entry); load() re-attaches orphans at the end of the order. A crash
    mid-append leaves a truncated final line, which load() drops.

    The legacy single-file JSON database is imported transparently on load.
    """

    TXS_FILENAME = "transactions"
    ORDER_FILENAME = "txsOrder"

    def __init__(self, path, legacyFile=None):
        self.path = path
        # optional explicit path to a legacy single-file JSON database
        # (e.g. config["dataBaseFile"]), imported by _importLegacyIfNeeded()
        self._extraLegacyPaths = [legacyFile] if legacyFile else []
        self.transactions = {}
        self.txsOrder = []
        self._lock = threading.Lock()
        # files opened lazily by save() and kept open for appends
        self._txsFile = None
        self._orderFile = None
        # number of tail transactions already appended to disk
        self._savedCount = 0

    # PATH HELPERS

    def _dirPath(self):
        return os.path.abspath(self.path)

    def _txsPath(self):
        return os.path.join(self._dirPath(), self.TXS_FILENAME)

    def _orderPath(self):
        return os.path.join(self._dirPath(), self.ORDER_FILENAME)

    def _legacyJsonPaths(self):
        # only the file explicitly named in the config (dataBaseFile).
        # .bak files are operator-made backups and are deliberately never
        # touched by the import.
        return list(self._extraLegacyPaths)

    # LOADING

    def load(self):
        """Load the database from disk into memory. Raises on failure.

        Imports the legacy JSON database first if it exists, then reads the
        line-oriented files. Tolerates a truncated final line in either file
        (crash mid-append).

        The transactions dict and txsOrder list are loaded independently: a
        transaction may exist in the dict without being in the order (an
        "orphan"). This is a valid state, not corruption — the dict is a
        hash->data store, while txsOrder is the source of truth for chain
        history. Orphans are NOT re-attached to the order here; doing so would
        silently mutate chain history on every restart.
        """
        with self._lock:
            self._importLegacyIfNeeded()
            if not os.path.isdir(self._dirPath()):
                raise FileNotFoundError(self._dirPath())
            self.transactions = {}
            self.txsOrder = []
            with open(self._txsPath(), "r") as file:
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        tx = json.loads(line)
                        txHash = tx["hash"]
                    except (ValueError, KeyError, TypeError):
                        # torn write from a crash mid-append. Skip the bad line
                        # and keep reading: a failed save() re-appends its whole
                        # batch, so any incompletely-written tx has a clean
                        # duplicate further down. Stopping here instead would
                        # drop every transaction stored after the torn line.
                        continue
                    self.transactions[txHash] = tx
            with open(self._orderPath(), "r") as file:
                seen = set()
                for line in file:
                    txHash = line.strip()
                    if not txHash or txHash in seen:
                        continue  # tolerate duplicates defensively
                    self.txsOrder.append(txHash)
                    seen.add(txHash)
            self._savedCount = len(self.txsOrder)

    def _importLegacyIfNeeded(self):
        """Import a legacy single-file JSON database into the new layout.

        Only runs when no converted database exists yet: importing over an
        existing data dir would destroy newer data with an older snapshot.
        """
        if os.path.isfile(self._txsPath()) or os.path.isfile(self._orderPath()):
            return
        for legacyPath in self._legacyJsonPaths():
            if not os.path.isfile(legacyPath):
                continue
            try:
                with open(legacyPath, "r") as file:
                    db = json.load(file)
                legacyTxs = db["transactions"]
                legacyOrder = db["txsOrder"]
            except (ValueError, KeyError, OSError):
                continue  # unreadable/absent legacy file: ignore it
            os.makedirs(self._dirPath(), exist_ok=True)
            # Write the full transactions dict (hash->data store) independently
            # of the order: every tx in the legacy dict is preserved, including
            # any that the legacy order did not reference (orphans). The dict is
            # a lookup table, not chain history, so order is irrelevant here.
            with open(self._txsPath(), "w") as file:
                for txHash, tx in legacyTxs.items():
                    file.write(json.dumps(tx) + "\n")
                file.flush()
                os.fsync(file.fileno())
            # Write txsOrder verbatim from the legacy order, but drop any entry
            # whose hash has no data in the dict (a dangling order entry is
            # genuinely corrupt and would index into a missing tx).
            with open(self._orderPath(), "w") as file:
                for txHash in legacyOrder:
                    if txHash in legacyTxs:
                        file.write(txHash + "\n")
                file.flush()
                os.fsync(file.fileno())
            shutil.move(legacyPath, legacyPath + ".imported")
            print(f"Imported legacy database {os.path.basename(legacyPath)} into {os.path.basename(self._dirPath())}/")
            return

    # IN-MEMORY OPERATIONS

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

    def getOrderedTxs(self):
        """Return [(hash, tx), ...] as one consistent snapshot."""
        with self._lock:
            return [(h, self.transactions.get(h)) for h in self.txsOrder]

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
        """Rewrite transaction payloads stored as dicts to compact JSON strings.

        Mutating stored transactions makes them diverge from the append-only
        file, so a full rewrite of the transactions file follows.
        """
        with self._lock:
            mutated = False
            for txid in self.txsOrder:
                tx = self.transactions.get(txid)
                if tx and type(tx["data"]) == dict:
                    tx["data"] = json.dumps(tx["data"]).replace(" ", "")
                    mutated = True
            if mutated and os.path.isdir(self._dirPath()):
                self._rewriteTransactionsFile()

    # SAVING

    def save(self):
        """Durably persist newly added transactions to disk.

        Appends one JSON line per new transaction to "transactions", fsyncs,
        then appends their hashes to "txsOrder", fsyncs. Writing in this order
        guarantees that a crash can only leave an orphaned transaction (fixed
        up by load()), never a dangling order entry. Cost is O(new txs), not
        O(total database size).

        A lock serializes concurrent saves (HTTP handlers + background
        routine) and keeps the append-only file handles consistent.
        """
        with self._lock:
            startIdx = self._savedCount
            if startIdx >= len(self.txsOrder):
                return  # nothing new since last save
            dirPath = self._dirPath()
            os.makedirs(dirPath, exist_ok=True)
            if self._txsFile is None:
                self._txsFile = open(self._txsPath(), "a")
                self._orderFile = open(self._orderPath(), "a")
                # the files' directory entries must be durable too, otherwise
                # a power loss right after the very first save can make one
                # file vanish while the other survives
                self._fsyncDir()
            try:
                for txHash in self.txsOrder[startIdx:]:
                    tx = self.transactions[txHash]
                    self._txsFile.write(json.dumps(tx) + "\n")
                self._txsFile.flush()
                os.fsync(self._txsFile.fileno())
                for txHash in self.txsOrder[startIdx:]:
                    self._orderFile.write(txHash + "\n")
                self._orderFile.flush()
                os.fsync(self._orderFile.fileno())
                self._savedCount = len(self.txsOrder)
            except BaseException:
                # drop the append handles so a later save() reopens cleanly;
                # unsaved txs stay in memory and are retried next time
                self._closeAppendFiles()
                raise

    def _fsyncDir(self):
        """Best-effort fsync of the data directory (not all filesystems support it)."""
        try:
            dirFd = os.open(self._dirPath(), os.O_RDONLY)
            try:
                os.fsync(dirFd)
            finally:
                os.close(dirFd)
        except OSError:
            pass

    def _closeAppendFiles(self):
        for attr in ("_txsFile", "_orderFile"):
            file = getattr(self, attr)
            if file is not None:
                try:
                    file.close()
                except OSError:
                    pass
                setattr(self, attr, None)

    def _rewriteTransactionsFile(self):
        """Atomically rewrite the transactions file (tmp + fsync + rename).

        Used when stored transactions are mutated in place; the order file is
        untouched since hashes don't change. The append handles are dropped so
        the next save() reopens them (their positions are stale after a rewrite).
        """
        self._closeAppendFiles()
        dirPath = self._dirPath()
        fd, tmpPath = tempfile.mkstemp(prefix=self.TXS_FILENAME + ".", suffix=".tmp", dir=dirPath)
        try:
            with os.fdopen(fd, "w") as file:
                for txHash in self.txsOrder:
                    tx = self.transactions.get(txHash)
                    if tx is not None:
                        file.write(json.dumps(tx) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmpPath, self._txsPath())
        except BaseException:
            try:
                os.unlink(tmpPath)
            except OSError:
                pass
            raise
