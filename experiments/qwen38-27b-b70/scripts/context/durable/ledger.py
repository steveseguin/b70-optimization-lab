"""Host-owned canonical deliveries and transactional quoted-event bookkeeping.

The runner commits deliver() before exposing its returned text to the model. Keep
the database outside any agent filesystem/tool interface: file permissions alone
cannot isolate a model allowed to run arbitrary commands as the host user.

Quotes and amounts are checked against immutable delivered text, never against an
editable transcript or model-supplied replacement. These checks establish source
provenance and arithmetic, not semantic correctness or extraction completeness.
An operation can still misinterpret a valid quote. Independently grade answers.

Pilot restrictions: operations are set/add/sub/remove/reopen, amounts must occur
in the source, and quote positions must be nondecreasing within a batch. Relative
operations such as doubling are not inferred. Identical event signatures are
rejected even if the source repeats an identical sentence: future support needs
explicit occurrence offsets. Whitespace-normalized quotes use their first source
occurrence, so repeated sentences can also cause a conservative order rejection.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3


class LedgerError(Exception):
    """Base class for expected ledger validation, conflict, and storage failures."""


class ValidationError(LedgerError):
    pass


class ConflictError(LedgerError):
    pass


class OrderError(LedgerError):
    pass


class StorageError(LedgerError):
    pass


_NAME = re.compile(r"[a-z]+[0-9]{2}\Z")
_OPS = {"set", "add", "sub", "remove", "reopen"}
_FINAL = {"QUERY", "GET"}
_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_UNITS.update({w: i * 10 for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i > 1})


def numbers(text):
    """Read signed digits and ordinary English integers, preserving punctuation stops.

    Adapted from the lab's ctxfold.py number reader. It deliberately does not parse
    a dozen, fractions, spelled arithmetic or other relative expressions.
    """
    text = re.sub(r"\b[a-z]+[0-9]{2}\b", " ", text.lower())
    tokens = re.findall(r"-?[0-9]+|[a-z]+(?:-[a-z]+)*|[.,;:!?]", text)
    output, i = [], 0
    while i < len(tokens):
        token = tokens[i]
        if re.fullmatch(r"-?[0-9]+", token):
            output.append(int(token))
            i += 1
            continue
        negative = token == "minus"
        j = i + 1 if negative else i
        total, current, used = 0, 0, False
        while j < len(tokens):
            word = tokens[j]
            pieces = word.split("-")
            if all(piece in _UNITS for piece in pieces):
                value = sum(_UNITS[piece] for piece in pieces)
                if used and current % 100 and (value >= 10 or current % 10):
                    break
                current += value
                used = True
            elif word == "hundred" and used and current < 100:
                current *= 100
            elif word == "thousand" and used:
                total += current * 1000
                current = 0
            elif (word == "and" and used and j + 1 < len(tokens)
                  and tokens[j + 1].split("-")[0] in _UNITS):
                pass
            else:
                break
            j += 1
        if used:
            output.append(-(total + current) if negative else total + current)
            i = j
        else:
            i += 1
    return output


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalized(text):
    return " ".join(text.split())


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


_SCHEMA = (
    """CREATE TABLE deliveries (
        batch_id INTEGER PRIMARY KEY CHECK(batch_id > 0),
        kind TEXT NOT NULL CHECK(kind IN ('UPDATE', 'QUERY', 'GET')),
        text TEXT NOT NULL, sha256 TEXT NOT NULL, delivered_at TEXT NOT NULL
    )""",
    """CREATE TABLE current_state (counter TEXT PRIMARY KEY, value TEXT)""",
    """CREATE TABLE events (
        event_id TEXT PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES deliveries(batch_id),
        ordinal INTEGER NOT NULL CHECK(ordinal >= 0), payload TEXT NOT NULL,
        source_start INTEGER NOT NULL, source_end INTEGER NOT NULL,
        UNIQUE(batch_id, ordinal)
    )""",
    """CREATE TABLE receipts (
        batch_id INTEGER PRIMARY KEY REFERENCES deliveries(batch_id),
        delivery_sha256 TEXT NOT NULL, events_sha256 TEXT NOT NULL,
        events_applied INTEGER NOT NULL, state_sha256 TEXT NOT NULL, applied_at TEXT NOT NULL
    )""",
)


class CanonicalLedger:
    """Durable ledger with JSON-friendly return values and explicit close/context support.

    Delivery IDs are contiguous positive integers starting at 1. Exact redelivery
    is idempotent; conflicting ID reuse is rejected. A final QUERY/GET may follow
    updates and is retrievable, but is never applied. No new delivery follows it.

    Event input: {id: str, counter: str, op: str, amount: int|None, quote: str}.
    IDs are globally unique. Reapplying an already committed batch is idempotent
    only with the same normalized event list, including IDs and order.
    """

    def __init__(self, db_path):
        path = Path(db_path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                raise StorageError("Database must be a regular host-owned file")
            if path.stat().st_mode & 0o077:
                raise StorageError("Existing database permissions must restrict access to its owner")
        else:
            os.close(fd)
        self._conn = None
        try:
            self._conn = sqlite3.connect(path, timeout=10, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            with self._transaction():
                version = self._conn.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    for statement in _SCHEMA:
                        self._conn.execute(statement)
                    for table in ("deliveries", "events", "receipts"):
                        for action in ("UPDATE", "DELETE"):
                            self._conn.execute(
                                f"CREATE TRIGGER immutable_{table}_{action.lower()} "
                                f"BEFORE {action} ON {table} BEGIN "
                                "SELECT RAISE(ABORT, 'immutable ledger record'); END"
                            )
                    self._conn.execute("PRAGMA user_version=1")
                elif version != 1:
                    raise StorageError(f"Unsupported ledger schema version {version}")
        except (sqlite3.Error, OSError) as exc:
            self.close()
            raise StorageError("Unable to initialize canonical ledger") from exc
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def _transaction(self):
        if self._conn is None:
            raise StorageError("Ledger is closed")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            yield
            self._conn.execute("COMMIT")
        except BaseException as exc:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            if isinstance(exc, sqlite3.Error):
                raise StorageError("Ledger transaction failed; no changes committed") from exc
            raise

    @staticmethod
    def _batch_id(batch_id):
        if type(batch_id) is not int or not 0 < batch_id < 2**63:
            raise ValidationError("batch_id must be a positive 64-bit integer")

    def _delivery(self, batch_id):
        self._batch_id(batch_id)
        row = self._conn.execute("SELECT * FROM deliveries WHERE batch_id=?", (batch_id,)).fetchone()
        if row is None:
            raise ValidationError(f"Batch {batch_id} has not been delivered")
        return dict(row)

    def deliver(self, batch_id, text, *, kind="UPDATE"):
        """Commit original bytes before returning text that the runner can expose."""
        self._batch_id(batch_id)
        if not isinstance(text, str) or kind not in {"UPDATE", "QUERY", "GET"}:
            raise ValidationError("Delivery requires text and kind UPDATE, QUERY or GET")
        digest = _hash(text)
        with self._transaction():
            existing = self._conn.execute("SELECT * FROM deliveries WHERE batch_id=?", (batch_id,)).fetchone()
            if existing:
                result = dict(existing)
                if result["text"] != text or result["kind"] != kind or result["sha256"] != digest:
                    raise ConflictError(f"Batch {batch_id} already has different canonical content")
                result["replayed"] = True
                return result
            next_id = self._conn.execute("SELECT COALESCE(MAX(batch_id), 0) + 1 FROM deliveries").fetchone()[0]
            if batch_id != next_id:
                raise OrderError(f"Expected delivery {next_id}, got {batch_id}")
            if self._conn.execute("SELECT 1 FROM deliveries WHERE kind IN ('QUERY','GET')").fetchone():
                raise OrderError("No new delivery is allowed after the final questions")
            result = {"batch_id": batch_id, "kind": kind, "text": text, "sha256": digest,
                      "delivered_at": _now()}
            self._conn.execute("INSERT INTO deliveries VALUES (?, ?, ?, ?, ?)",
                               (batch_id, kind, text, digest, result["delivered_at"]))
            result["replayed"] = False
        return result

    def get(self, batch_id):
        """Return canonical source, including final questions, after a restart."""
        with self._transaction():
            result = self._delivery(batch_id)
            result["applied"] = self._conn.execute(
                "SELECT 1 FROM receipts WHERE batch_id=?", (batch_id,)).fetchone() is not None
        return result

    def recall(self, pattern, *, through_batch=None):
        """Literal, case-sensitive substring search; caller bounds exposed results.

        Searches original complete deliveries, including unprocessed batches. The
        runner must not pre-deliver future batches if early retrieval is forbidden.
        """
        if not isinstance(pattern, str) or not pattern:
            raise ValidationError("recall requires a nonempty literal substring")
        if through_batch is not None:
            self._batch_id(through_batch)
        with self._transaction():
            rows = self._conn.execute(
                "SELECT * FROM deliveries WHERE instr(text, ?) > 0 "
                "AND (? IS NULL OR batch_id <= ?) ORDER BY batch_id",
                (pattern, through_batch, through_batch)).fetchall()
            return [dict(row) for row in rows]

    def _state(self):
        return {row["counter"]: None if row["value"] is None else int(row["value"])
                for row in self._conn.execute("SELECT * FROM current_state ORDER BY counter")}

    def metadata(self):
        with self._transaction():
            delivered = [row[0] for row in self._conn.execute("SELECT batch_id FROM deliveries ORDER BY batch_id")]
            applied = [row[0] for row in self._conn.execute("SELECT batch_id FROM receipts ORDER BY batch_id")]
            pending = self._conn.execute(
                "SELECT MIN(batch_id) FROM deliveries WHERE kind='UPDATE' "
                "AND batch_id NOT IN (SELECT batch_id FROM receipts)").fetchone()[0]
            state = self._state()
            return {"schema_version": 1, "delivered_batches": delivered, "applied_batches": applied,
                    "next_delivery_id": (delivered[-1] + 1) if delivered else 1,
                    "next_pending_batch": pending, "state": state, "state_sha256": _hash(_json(state)),
                    "final_batch_id": self._conn.execute(
                        "SELECT batch_id FROM deliveries WHERE kind IN ('QUERY','GET')").fetchone()[0]
                    if self._conn.execute("SELECT 1 FROM deliveries WHERE kind IN ('QUERY','GET')").fetchone()
                    else None}

    def _receipt(self, batch_id):
        row = self._conn.execute("SELECT * FROM receipts WHERE batch_id=?", (batch_id,)).fetchone()
        return dict(row) if row else None

    def receipt(self, batch_id):
        self._batch_id(batch_id)
        with self._transaction():
            return self._receipt(batch_id)

    @staticmethod
    def _events(events):
        if not isinstance(events, list):
            raise ValidationError("events must be a list")
        normalized, ids, signatures = [], set(), set()
        required = {"id", "counter", "op", "amount", "quote"}
        for index, raw in enumerate(events):
            if not isinstance(raw, dict) or set(raw) != required:
                raise ValidationError(f"Event {index} must contain exactly {sorted(required)}")
            identifier, counter, op, amount, quote = (raw[k] for k in ("id", "counter", "op", "amount", "quote"))
            if not isinstance(identifier, str) or not identifier or len(identifier) > 256:
                raise ValidationError(f"Event {index} needs a nonempty string id of at most 256 characters")
            if identifier in ids:
                raise ConflictError(f"Duplicate event id {identifier}")
            ids.add(identifier)
            if not isinstance(counter, str) or not _NAME.fullmatch(counter):
                raise ValidationError(f"Event {identifier} has an invalid counter name")
            if not isinstance(op, str) or op not in _OPS:
                raise ValidationError(f"Event {identifier} has an unsupported operation")
            if ((op == "remove" and amount is not None)
                    or (op != "remove" and type(amount) is not int)
                    or (op in {"add", "sub"} and amount <= 0)):
                raise ValidationError(f"Event {identifier} needs an integer amount (positive for add/sub), or null for remove")
            if not isinstance(quote, str) or not _normalized(quote):
                raise ValidationError(f"Event {identifier} needs a nonempty source quote")
            quote = _normalized(quote)
            signature = (counter, op, amount, quote)
            if signature in signatures:
                raise ConflictError("Duplicate event content under different ids; source occurrence offsets are required")
            signatures.add(signature)
            normalized.append({"id": identifier, "counter": counter, "op": op, "amount": amount, "quote": quote})
        return normalized

    @staticmethod
    def _verify_source(source, events):
        canonical = _normalized(source)
        paragraphs = [_normalized(p) for p in re.split(r"\n\s*\n", source) if p.strip()]
        sentences = _sentences(canonical)
        named = set(re.findall(r"\b[a-z]+[0-9]{2}\b", source))
        offsets, previous = [], -1
        for event in events:
            identifier, counter, quote, amount = (event[k] for k in ("id", "counter", "quote", "amount"))
            if counter not in named:
                raise ValidationError(f"Event {identifier}: counter is absent from canonical delivery")
            offset = canonical.find(quote)
            if offset < 0:
                raise ValidationError(f"Event {identifier}: quote is absent from canonical delivery")
            if offset < previous:
                raise OrderError(f"Event {identifier}: quotes are out of canonical source order")
            previous = offset
            offsets.append((offset, offset + len(quote)))
            if event["op"] == "remove":
                continue
            candidates = {n for sentence in sentences if quote in sentence or sentence in quote
                          for n in numbers(sentence)}
            for paragraph in paragraphs:
                if quote in paragraph:
                    for sentence in _sentences(paragraph):
                        if (quote in sentence or sentence in quote
                                or re.search(r"\b" + re.escape(counter) + r"\b", sentence)):
                            candidates.update(numbers(sentence))
            if amount not in candidates:
                raise ValidationError(f"Event {identifier}: amount is absent from the quoted sentence or its counter's paragraph")
        return offsets

    def apply(self, batch_id, events):
        """Validate then atomically commit events, new state and a durable receipt.

        An empty event list explicitly means no changes; the ledger does not infer
        whether omitted changes existed. Replay returns the original receipt with
        replayed=True and never reapplies arithmetic.
        """
        self._batch_id(batch_id)
        events = self._events(events)
        digest = _hash(_json(events))
        with self._transaction():
            source = self._delivery(batch_id)
            old_receipt = self._receipt(batch_id)
            if old_receipt:
                if old_receipt["events_sha256"] != digest:
                    raise ConflictError(f"Batch {batch_id} was already applied with different events")
                return dict(old_receipt, replayed=True)
            if source["kind"] != "UPDATE":
                raise ValidationError("Final questions are retrievable but cannot be applied as updates")
            next_batch = self._conn.execute(
                "SELECT MIN(batch_id) FROM deliveries WHERE kind='UPDATE' "
                "AND batch_id NOT IN (SELECT batch_id FROM receipts)").fetchone()[0]
            if batch_id != next_batch:
                raise OrderError(f"Batch {next_batch} must be applied before batch {batch_id}")
            for event in events:
                if self._conn.execute("SELECT 1 FROM events WHERE event_id=?", (event["id"],)).fetchone():
                    raise ConflictError(f"Event id {event['id']} belongs to an already committed batch")
            offsets = self._verify_source(source["text"], events)
            state = self._state()
            for ordinal, (event, offset) in enumerate(zip(events, offsets)):
                name, op, amount = event["counter"], event["op"], event["amount"]
                live = state.get(name) is not None
                if op in {"add", "sub", "remove"} and not live:
                    raise ValidationError(f"Event {event['id']}: {op} requires a live counter")
                if op == "reopen" and live:
                    raise ValidationError(f"Event {event['id']}: reopen requires a new or removed counter")
                if op in {"set", "reopen"}:
                    state[name] = amount
                elif op == "add":
                    state[name] += amount
                elif op == "sub":
                    state[name] -= amount
                else:
                    state[name] = None
                self._conn.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                                   (event["id"], batch_id, ordinal, _json(event), *offset))
                self._conn.execute("INSERT INTO current_state VALUES (?, ?) ON CONFLICT(counter) "
                                   "DO UPDATE SET value=excluded.value",
                                   (name, None if state[name] is None else str(state[name])))
            receipt = {"batch_id": batch_id, "delivery_sha256": source["sha256"], "events_sha256": digest,
                       "events_applied": len(events), "state_sha256": _hash(_json(state)), "applied_at": _now()}
            self._conn.execute("INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?)",
                               tuple(receipt[k] for k in ("batch_id", "delivery_sha256", "events_sha256",
                                                        "events_applied", "state_sha256", "applied_at")))
        return dict(receipt, replayed=False)
