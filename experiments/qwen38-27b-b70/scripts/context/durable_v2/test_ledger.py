"""CPU-only durability, provenance and ordering tests; all databases are temporary.

Run: python3 -m unittest discover -s experiments/qwen38-27b-b70/scripts/context/durable -p test_ledger.py -v
"""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from ledger import (CanonicalLedger, ConflictError, LedgerError, OrderError,
                    StorageError, ValidationError, numbers)


def event(identifier="1:0", counter="abcd12", op="set", amount=10,
          quote="abcd12 was set to 10."):
    return {"id": identifier, "counter": counter, "op": op, "amount": amount, "quote": quote}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="canonical-ledger-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "private" / "ledger.sqlite"
        self.ledger = self.open()

    def open(self):
        store = CanonicalLedger(self.path)
        self.addCleanup(store.close)
        return store

    def test_delivery_is_committed_immutable_and_survives_restart(self):
        text = "abcd12 was set to 10.\n\nExact original text: café.\n"
        delivered = self.ledger.deliver(1, text)
        self.assertEqual(delivered["sha256"], hashlib.sha256(text.encode()).hexdigest())
        observer = self.open()
        self.assertEqual(observer.get(1)["text"], text)  # committed before deliver returns
        self.assertFalse(observer.get(1)["applied"])
        for sql in ("UPDATE deliveries SET text='edited' WHERE batch_id=1",
                    "DELETE FROM deliveries WHERE batch_id=1"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.ledger._conn.execute(sql)
        self.ledger.close()
        self.assertEqual(self.open().get(1)["text"], text)

    def test_exact_redelivery_is_idempotent_conflicting_content_rejected(self):
        first = self.ledger.deliver(1, "original")
        second = self.ledger.deliver(1, "original")
        self.assertFalse(first.pop("replayed"))
        self.assertTrue(second.pop("replayed"))
        self.assertEqual(first, second)
        for content, kind in (("edited", "UPDATE"), ("original", "QUERY")):
            with self.assertRaises(ConflictError):
                self.ledger.deliver(1, content, kind=kind)
        self.assertEqual(self.ledger.metadata()["delivered_batches"], [1])

    def test_delivery_must_be_contiguous_and_cannot_follow_final(self):
        with self.assertRaises(OrderError):
            self.ledger.deliver(2, "future")
        self.ledger.deliver(1, "No changes.")
        self.ledger.deliver(2, "QUERY abcd12", kind="QUERY")
        with self.assertRaises(OrderError):
            self.ledger.deliver(3, "too late")
        self.assertEqual(self.ledger.metadata()["final_batch_id"], 2)

    def test_restart_replay_keeps_arithmetic_and_receipt_exact(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        first = self.ledger.apply(1, [event()])
        self.assertFalse(first["replayed"])
        self.ledger.deliver(2, "abcd12 went up by 5.")
        addition = event("2:0", op="add", amount=5, quote="abcd12 went up by 5.")
        second = self.ledger.apply(2, [addition])
        self.ledger.close()
        restarted = self.open()
        replay = restarted.apply(2, [addition])
        self.assertTrue(replay.pop("replayed"))
        second.pop("replayed")
        self.assertEqual(replay, second)
        self.assertEqual(restarted.receipt(2), second)
        self.assertEqual(restarted.metadata()["state"], {"abcd12": 15})
        self.assertEqual(restarted.metadata()["applied_batches"], [1, 2])
        self.assertIsNone(restarted.metadata()["next_pending_batch"])

    def test_changed_replay_is_rejected_even_if_same_result(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        self.ledger.apply(1, [event()])
        with self.assertRaises(ConflictError):
            self.ledger.apply(1, [event("new-id")])
        self.assertEqual(self.ledger.metadata()["state"], {"abcd12": 10})

    def test_duplicate_ids_and_duplicate_payloads_rejected(self):
        source = "abcd12 was set to 10. abcd12 went up by 5."
        self.ledger.deliver(1, source)
        duplicate_id = event(op="add", amount=5, quote="abcd12 went up by 5.")
        duplicate_payload = event("different-id")
        for changes in ([event(), duplicate_id], [event(), duplicate_payload]):
            with self.subTest(changes=changes), self.assertRaises(ConflictError):
                self.ledger.apply(1, changes)
        self.assertEqual(self.ledger.metadata()["state"], {})
        self.assertIsNone(self.ledger.receipt(1))

    def test_event_ids_are_globally_unique_across_batches(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        self.ledger.apply(1, [event()])
        self.ledger.deliver(2, "abcd12 went up by 5.")
        with self.assertRaises(ConflictError):
            self.ledger.apply(2, [event(op="add", amount=5, quote="abcd12 went up by 5.")])
        self.assertEqual(self.ledger.metadata()["state"], {"abcd12": 10})

    def test_out_of_order_batch_does_not_mutate_state(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        self.ledger.deliver(2, "abcd12 went up by 5.")
        addition = event("2:0", op="add", amount=5, quote="abcd12 went up by 5.")
        with self.assertRaises(OrderError):
            self.ledger.apply(2, [addition])
        self.assertEqual(self.ledger.metadata()["state"], {})
        self.assertIsNone(self.ledger.receipt(2))
        self.ledger.apply(1, [event()])
        self.ledger.apply(2, [addition])
        self.assertEqual(self.ledger.metadata()["state"], {"abcd12": 15})

    def test_reversed_source_quotes_are_rejected_atomically(self):
        self.ledger.deliver(1, "abcd12 was set to 10. abcd12 went up by 5.")
        addition = event("1:1", op="add", amount=5, quote="abcd12 went up by 5.")
        with self.assertRaises(OrderError):
            self.ledger.apply(1, [addition, event()])
        self.assertEqual(self.ledger.metadata()["state"], {})
        self.assertIsNone(self.ledger.receipt(1))

    def test_model_edited_text_has_no_authority(self):
        delivery = self.ledger.deliver(1, "abcd12 was set to 10.")
        delivery["text"] = "abcd12 was set to 999."
        with self.assertRaises(ValidationError):
            self.ledger.apply(1, [event(amount=999, quote=delivery["text"])])
        self.assertEqual(self.ledger.get(1)["text"], "abcd12 was set to 10.")
        self.assertEqual(self.ledger.metadata()["state"], {})
        self.ledger.apply(1, [event()])

    def test_bad_later_quote_rejects_whole_list(self):
        self.ledger.deliver(1, "abcd12 was set to 10. efgh34 was set to 20.")
        bad = event("1:1", "efgh34", amount=20, quote="efgh34 was set to 999.")
        with self.assertRaises(ValidationError):
            self.ledger.apply(1, [event(), bad])
        self.assertEqual(self.ledger.metadata()["state"], {})
        self.assertEqual(self.ledger._conn.execute("SELECT count(*) FROM events").fetchone()[0], 0)

    def test_invalid_later_state_transition_rolls_back_prior_event(self):
        self.ledger.deliver(1, "abcd12 was set to 10. efgh34 went up by 20.")
        bad = event("1:1", "efgh34", op="add", amount=20, quote="efgh34 went up by 20.")
        with self.assertRaises(ValidationError):
            self.ledger.apply(1, [event(), bad])
        self.assertEqual(self.ledger.metadata()["state"], {})
        self.assertEqual(self.ledger._conn.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.assertIsNone(self.ledger.receipt(1))

    def test_database_failure_rolls_back_state_events_and_receipt(self):
        self.ledger.deliver(1, "abcd12 was set to 10. efgh34 was set to 20.")
        changes = [event(), event("1:1", "efgh34", amount=20, quote="efgh34 was set to 20.")]
        self.ledger._conn.execute(
            "CREATE TEMP TRIGGER fail_second_event AFTER INSERT ON events WHEN NEW.ordinal=1 "
            "BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END")
        with self.assertRaises(StorageError):
            self.ledger.apply(1, changes)
        self.ledger.close()  # also removes the temporary injected-failure trigger
        restarted = self.open()
        self.assertEqual(restarted.metadata()["state"], {})
        self.assertEqual(restarted._conn.execute("SELECT count(*) FROM events").fetchone()[0], 0)
        self.assertIsNone(restarted.receipt(1))
        self.assertEqual(restarted.metadata()["next_pending_batch"], 1)
        restarted.apply(1, changes)
        self.assertEqual(restarted.metadata()["state"], {"abcd12": 10, "efgh34": 20})

    def test_process_exit_during_transaction_recovers_original_delivery(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        self.ledger.close()
        child = """
import json, os, sys
sys.path.insert(0, sys.argv[1])
from ledger import CanonicalLedger
store = CanonicalLedger(sys.argv[2])
store._conn.create_function('test_crash', 0, lambda: os._exit(91))
store._conn.execute('CREATE TEMP TRIGGER crash AFTER INSERT ON current_state BEGIN SELECT test_crash(); END')
store.apply(1, json.loads(sys.argv[3]))
"""
        result = subprocess.run([sys.executable, "-c", child, str(Path(__file__).parent),
                                 str(self.path), json.dumps([event()])], capture_output=True, text=True,
                                timeout=15)
        self.assertEqual(result.returncode, 91, result.stderr)
        restarted = self.open()
        self.assertEqual(restarted.get(1)["text"], "abcd12 was set to 10.")
        self.assertEqual(restarted.metadata()["state"], {})
        self.assertIsNone(restarted.receipt(1))
        restarted.apply(1, [event()])
        self.assertEqual(restarted.metadata()["state"], {"abcd12": 10})

    def test_literal_recall_uses_canonical_source_and_batch_bound(self):
        original = "abcd12 was set to 10. Literal markers: %_."
        self.ledger.deliver(1, original)
        self.ledger.apply(1, [event()])
        self.ledger.deliver(2, "abcd12 went up by 5.")
        self.assertEqual([x["batch_id"] for x in self.ledger.recall("abcd12")], [1, 2])
        self.assertEqual(self.ledger.recall("abcd12", through_batch=1)[0]["text"], original)
        self.assertEqual(len(self.ledger.recall("%_")), 1)
        self.assertEqual(self.ledger.recall(".*"), [])
        self.assertEqual(self.ledger.recall("ABCD12"), [])
        self.assertEqual(self.ledger.recall("999"), [])

    def test_final_questions_are_persisted_but_not_applied(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        self.ledger.deliver(2, "QUERY abcd12", kind="QUERY")
        self.ledger.apply(1, [event()])
        with self.assertRaises(ValidationError):
            self.ledger.apply(2, [])
        self.ledger.close()
        restarted = self.open()
        self.assertEqual(restarted.get(2)["text"], "QUERY abcd12")
        self.assertEqual(restarted.metadata()["applied_batches"], [1])
        self.assertIsNone(restarted.metadata()["next_pending_batch"])

    def test_remove_reopen_and_big_integer_arithmetic_survive_restart(self):
        big = 10**30
        source = (f"abcd12 was set to {big}. abcd12 went up by 5. "
                  "abcd12 was removed. abcd12 reopened at minus seven.")
        changes = [event(amount=big, quote=f"abcd12 was set to {big}."),
                   event("1:1", op="add", amount=5, quote="abcd12 went up by 5."),
                   event("1:2", op="remove", amount=None, quote="abcd12 was removed."),
                   event("1:3", op="reopen", amount=-7, quote="abcd12 reopened at minus seven.")]
        self.ledger.deliver(1, source)
        self.ledger.apply(1, changes)
        self.assertEqual(self.ledger.metadata()["state"], {"abcd12": -7})
        self.ledger.close()
        self.assertEqual(self.open().metadata()["state"], {"abcd12": -7})

    def test_number_reader_preserves_punctuation_and_sign(self):
        self.assertEqual(numbers("abcd12 went down by eighty-three. Two packers arrived."), [83, 2])
        self.assertEqual(numbers("minus forty-two, three hundred and six; one thousand and seven."), [-42, 306, 1007])
        self.ledger.deliver(1, "abcd12 was set to eighty-three. Two packers arrived.")
        with self.assertRaises(ValidationError):
            self.ledger.apply(1, [event(amount=2, quote="abcd12 was set to eighty-three.")])
        self.ledger.apply(1, [event(amount=83, quote="abcd12 was set to eighty-three.")])

    def test_empty_batch_has_a_durable_idempotent_receipt(self):
        self.ledger.deliver(1, "Rain delayed the deliveries.")
        self.ledger.apply(1, [])
        self.assertEqual(self.ledger.receipt(1)["events_applied"], 0)
        self.assertTrue(self.ledger.apply(1, [])["replayed"])
        self.assertEqual(self.ledger.metadata()["state"], {})

    def test_database_and_sidecars_are_private_and_shared_file_refused(self):
        self.ledger.deliver(1, "persistent")
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        for filename in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            self.assertEqual(filename.stat().st_mode & 0o077, 0)
        self.ledger.close()
        self.path.chmod(0o644)
        with self.assertRaises(StorageError):
            CanonicalLedger(self.path)

    def test_context_manager_and_closed_store(self):
        self.ledger.close()
        with CanonicalLedger(self.path) as store:
            store.deliver(1, "saved")
        with self.assertRaises(StorageError):
            store.metadata()
        self.assertTrue(issubclass(ValidationError, LedgerError))

    def test_event_ids_and_receipts_remain_immutable(self):
        self.ledger.deliver(1, "abcd12 was set to 10.")
        self.ledger.apply(1, [event()])
        for sql in ("DELETE FROM events", "UPDATE events SET payload='{}'",
                    "DELETE FROM receipts", "UPDATE receipts SET events_applied=99"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.ledger._conn.execute(sql)
        saved = self.ledger._conn.execute("SELECT source_start, source_end FROM events").fetchone()
        self.assertEqual(tuple(saved), (0, len("abcd12 was set to 10.")))


if __name__ == "__main__":
    unittest.main()
