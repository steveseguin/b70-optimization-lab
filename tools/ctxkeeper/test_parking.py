import unittest

import parking as pk


def render(messages):
    # a stand-in chat template: role tags around each message, then the assistant opener
    return "".join(f"<{m['role']}>{m['content']}</{m['role']}>\n" for m in messages) + "<assistant>"


VOCAB: dict[str, int] = {}


def tokenize(text):
    return [VOCAB.setdefault(w, len(VOCAB) + 1) for w in text.replace("<", " <").replace(">", "> ").split()]


def turn(i):
    return [{"role": "user", "content": f"question {i}"}, {"role": "assistant", "content": f"answer {i}"}]


def reply(i):
    """The ids the engine generated for turn i's reply: the text after the opener, then the end tag, as the
    template renders a stored assistant turn."""
    return tokenize(f"answer {i}</assistant>\n")


def park(k, session, history):
    """Park at the end of the last turn of `history`: the prompt was everything before that reply."""
    return k.park(session, history[:-1], reply(len(history) // 2))


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 1.0
        return self.t


def keeper(engine=None, budget=10**12):
    engine = engine or pk.FakeEngine()
    events = []
    k = pk.Parking(engine, render, tokenize, budget_bytes=budget, clock=Clock(), log=events.append)
    return k, engine, events


class ParkingTests(unittest.TestCase):
    def test_no_checkpoint_means_prefill(self):
        k, _, _ = keeper()
        d = k.before_request("s1", turn(1))
        self.assertEqual((d.action, d.reason), ("prefill", "no checkpoint for this session"))

    def test_a_parked_turn_is_prompt_plus_generated_ids(self):
        k, eng, _ = keeper()
        p = park(k, "s1", turn(1))
        saved = eng.store[p.checkpoint_id]["token_state"]["token_history"]
        self.assertEqual(saved, k.prefix(turn(1)[:1]) + reply(1))
        self.assertEqual(saved, k.prefix(turn(1) + turn(2)[:1])[:len(saved)], "the next prompt extends it")

    def test_appended_turn_restores_and_appends_the_delta(self):
        k, eng, _ = keeper()
        view = turn(1)
        p = park(k, "s1", view)
        longer = view + turn(2)
        d = k.before_request("s1", longer)
        self.assertEqual(d.action, "restore")
        self.assertEqual(d.checkpoint_id, p.checkpoint_id)
        self.assertEqual(d.saved_tokens, p.tokens)
        self.assertEqual(d.saved_tokens + d.delta_tokens, len(k.prefix(longer)))
        self.assertGreater(d.delta_tokens, 0)
        # the runtime accepts exactly that: the saved part matches token for token
        r = eng.restore(d.checkpoint_id, k.prefix(longer))
        self.assertEqual(r, {"restored": d.saved_tokens, "appended": d.delta_tokens})

    def test_cut_inside_the_prefix_prefills_and_drops_the_checkpoint(self):
        k, eng, events = keeper()
        view = turn(1) + turn(2) + turn(3)
        p = park(k, "s1", view)
        # a notes cut rewrites the view early on: the saved prefix is no longer a prefix
        cut = [{"role": "user", "content": "NOTES: answers 1-2"}] + turn(3) + turn(4)
        d = k.before_request("s1", cut)
        self.assertEqual(d.action, "prefill")
        self.assertIn("not a prefix", d.reason)
        self.assertEqual(d.dropped, p.checkpoint_id)
        self.assertIsNone(eng.inspect(p.checkpoint_id))
        self.assertNotIn("s1", k.parked)
        self.assertEqual(events[-1]["event"], "checkpoint dropped")

    def test_shorter_prompt_prefills(self):
        k, _, _ = keeper()
        park(k, "s1", turn(1) + turn(2))
        d = k.before_request("s1", turn(1))
        self.assertEqual(d.action, "prefill")

    def test_same_prefix_restores_with_no_delta(self):
        k, _, _ = keeper()
        view = turn(1)
        park(k, "s1", view)
        d = k.before_request("s1", view + turn(2)[:1])
        self.assertEqual(d.action, "restore")
        self.assertEqual(d.delta_tokens, len(k.prefix(view + turn(2)[:1])) - d.saved_tokens)

    def test_model_or_engine_identity_change_prefills(self):
        for field in ("model", "engine"):
            k, eng, _ = keeper()
            park(k, "s1", turn(1))
            setattr(eng, field, f"{field}-b")
            d = k.before_request("s1", turn(1) + turn(2))
            self.assertEqual(d.action, "prefill")
            self.assertIn(f"{field} identity", d.reason)
            self.assertEqual(eng.store, {}, "the stale checkpoint was deleted")

    def test_unqualified_label_prefills(self):
        k, eng, _ = keeper(pk.FakeEngine(label="draft"))
        park(k, "s1", turn(1))
        self.assertEqual(k.before_request("s1", turn(1) + turn(2)).reason, "label differs from the running engine")

    def test_checkpoint_id_is_a_token_prefix_hash_not_a_json_hash(self):
        k, _, _ = keeper()
        a = [{"role": "user", "content": "x y"}]
        b = [{"role": "user", "content": "x  y"}]       # different JSON, same tokens
        self.assertEqual(k.checkpoint_id("s", k.prefix(a)), k.checkpoint_id("s", k.prefix(b)))
        c = [{"role": "user", "content": "x y z"}]
        self.assertNotEqual(k.checkpoint_id("s", k.prefix(a)), k.checkpoint_id("s", k.prefix(c)))

    def test_one_checkpoint_per_session_and_the_old_one_goes(self):
        k, eng, _ = keeper()
        first = park(k, "s1", turn(1))
        second = park(k, "s1", turn(1) + turn(2))
        self.assertNotEqual(first.checkpoint_id, second.checkpoint_id)
        self.assertEqual(set(eng.store), {second.checkpoint_id})
        self.assertIs(park(k, "s1", turn(1) + turn(2)), k.parked["s1"], "parking the same prefix again saves nothing")
        self.assertEqual([c for c in eng.calls if c[0] == "save"], [("save", first.checkpoint_id), ("save", second.checkpoint_id)])

    def test_eviction_is_least_recently_used_and_never_the_one_just_parked(self):
        eng = pk.FakeEngine(bytes_per_token=1, floor=100)
        k, _, events = keeper(eng, budget=250)
        park(k, "s1", turn(1))      # ~100 + n
        park(k, "s2", turn(2))
        self.assertEqual(k.before_request("s1", turn(1) + turn(2)).action, "restore")   # s1 used more recently than s2
        park(k, "s3", turn(3))      # over budget: s2 goes first
        self.assertEqual(set(k.parked), {"s1", "s3"})
        self.assertLessEqual(k.total_bytes(), 250)
        self.assertEqual([e["session"] for e in events if e["event"] == "checkpoint evicted"], ["s2"])

    def test_in_use_checkpoint_is_kept_and_deleted_later(self):
        eng = pk.FakeEngine(bytes_per_token=1, floor=100)
        k, _, _ = keeper(eng, budget=150)
        a = park(k, "s1", turn(1))
        eng.restore(a.checkpoint_id, k.prefix(turn(1) + turn(2)[:1]))   # the runtime holds it
        self.assertIsNone(park(k, "s2", turn(2)))                 # refuse SAVE while s1 pins the budget
        self.assertEqual([c for c in eng.calls if c[0] == "save"], [("save", a.checkpoint_id)])
        self.assertIn("s1", k.parked)
        self.assertEqual(k.status()["pending_delete"], [])     # eviction skipped it, no delete pending
        # a drop while in use: the policy forgets the session, the directory waits
        d = k.before_request("s1", turn(9))
        self.assertEqual(d.dropped, "kept: in_use")
        self.assertEqual(k.status()["pending_delete"], [a.checkpoint_id])
        self.assertEqual(k.total_bytes(), a.bytes, "detached in-use checkpoint still costs bytes")
        eng.release(a.checkpoint_id)
        park(k, "s3", turn(3))                                  # the next pass retries the delete
        self.assertNotIn(a.checkpoint_id, eng.store)
        self.assertEqual(k.status()["pending_delete"], [])

    def test_budget_and_native_ids_refuse_before_save(self):
        for budget in (-1, True, 1.5, "100"):
            with self.subTest(budget=budget), self.assertRaises(ValueError): keeper(budget=budget)
        k, eng, _ = keeper()
        for session in ("", ".hidden", "../x", "a/b", "é", "a"*40, "a.lock", "a\n"):
            with self.subTest(session=session), self.assertRaises(ValueError): park(k, session, turn(1))
        self.assertFalse(eng.calls)
        self.assertEqual(len(k.checkpoint_id("a"*39, [1])), 64)
        k, eng, _ = keeper(budget=0)
        self.assertIsNone(park(k, "s", turn(1))); self.assertFalse(eng.calls)

    def test_p198_requires_explicit_exact_contract_and_engine_identity(self):
        engine = pk.FakeEngine(label="experimental-postreply-front")
        k, _, _ = keeper(engine)
        p = park(k, "s", turn(1)); manifest = engine.store[p.checkpoint_id]
        manifest['contract'] = 'v1.2+p198'
        self.assertEqual(k.compatible(manifest), 'label')
        accepted = {('experimental-postreply-front', 'v1.2+p198')}
        explicit = pk.Parking(engine, render, tokenize, budget_bytes=10**12, accepted_contracts=accepted)
        accepted.clear()  # Constructor takes a copy of trusted configuration.
        self.assertIsNone(explicit.compatible(manifest))
        self.assertEqual(manifest['label'], 'experimental-postreply-front')
        manifest['contract'] = 'v1.2+p197'
        self.assertEqual(explicit.compatible(manifest), 'label/contract')
        manifest['contract'] = 'v1.2+p198'; manifest['engine']['binary_sha256'] = 'other'
        self.assertEqual(explicit.compatible(manifest), 'engine identity')
        with self.assertRaises(ValueError):
            pk.Parking(engine, render, tokenize, budget_bytes=100, accepted_contracts={('experimental',)})

    def test_missing_size_admission_refuses_save_and_explicit_fallback_admits(self):
        engine = pk.FakeEngine(bytes_per_token=0, floor=100)
        engine.save_size_bound = None
        k, _, _ = keeper(engine)
        self.assertIsNone(park(k, 's', turn(1))); self.assertFalse(engine.calls)
        k = pk.Parking(engine, render, tokenize, budget_bytes=150, save_reservation_bytes=120)
        p = park(k, 's', turn(1)); self.assertEqual(p.bytes, 120)
        for bound in (0, -1, True, 1.5):
            with self.subTest(bound=bound), self.assertRaises(ValueError):
                pk.Parking(engine, render, tokenize, budget_bytes=100, save_reservation_bytes=bound)

    def test_engine_bound_has_priority_and_invalid_bound_never_saves(self):
        engine = pk.FakeEngine(bytes_per_token=0, floor=100)
        k = pk.Parking(engine, render, tokenize, budget_bytes=150, save_reservation_bytes=1)
        self.assertEqual(park(k, 's', turn(1)).bytes, 100)
        for bound in (True, -1, 0, '100'):
            engine = pk.FakeEngine()
            engine.save_size_bound = lambda cid,tokens: bound
            k, _, _ = keeper(engine)
            with self.subTest(bound=bound), self.assertRaises(ValueError): park(k, 's', turn(1))
            self.assertFalse(engine.calls)

    def test_same_id_reinspects_missing_and_corrupt_checkpoint(self):
        for change in ('missing', 'model', 'prefix'):
            k, engine, _ = keeper(); first = park(k, 's', turn(1)); engine.calls.clear()
            if change == 'missing': del engine.store[first.checkpoint_id]
            elif change == 'model': engine.store[first.checkpoint_id]['model']['identity_tsv_sha256'] = 'changed'
            else: engine.store[first.checkpoint_id]['token_state']['tokens_sha256'] = '0'*64
            result = park(k, 's', turn(1))
            self.assertEqual(engine.calls[0], ('inspect', first.checkpoint_id))
            if change == 'missing': self.assertIsNotNone(result)
            else:
                self.assertIsNone(result)
                self.assertFalse(any(op=='save' for op,cid in engine.calls))

    def test_oversized_state_refuses_before_eviction_or_save(self):
        engine = pk.FakeEngine(bytes_per_token=0, floor=100)
        k, _, _ = keeper(engine, budget=150); p = park(k, 's', turn(1)); engine.calls.clear()
        engine.floor = 151
        self.assertIsNone(park(k, 'other', turn(2)))
        self.assertFalse(engine.calls); self.assertIs(k.parked['s'], p)

    def test_old_checkpoint_coexistence_must_fit_before_new_save(self):
        engine = pk.FakeEngine(bytes_per_token=0, floor=100)
        k, _, _ = keeper(engine, budget=150); old = park(k, 's', turn(1)); engine.calls.clear()
        self.assertIsNone(park(k, 's', turn(1)+turn(2)))
        self.assertIs(k.parked['s'], old); self.assertFalse(engine.calls)
        self.assertEqual(k.total_bytes(), 100)

    def test_replaced_in_use_old_state_stays_charged_without_double_count(self):
        engine = pk.FakeEngine(bytes_per_token=0, floor=100)
        k, _, _ = keeper(engine, budget=250); old = park(k, 's', turn(1)); engine.in_use.add(old.checkpoint_id)
        new = park(k, 's', turn(1)+turn(2))
        self.assertEqual(k.total_bytes(), 200)
        self.assertEqual(k.status()['retained_bytes'], {old.checkpoint_id:100})
        engine.in_use.add(new.checkpoint_id)
        self.assertIsNone(park(k, 'other', turn(3)))
        self.assertEqual(k.total_bytes(), 200)
        engine.release(old.checkpoint_id); k.retry_deletes()
        self.assertEqual(k.total_bytes(), 100)

    def test_lru_evicts_before_save_peak_never_exceeds_budget(self):
        class BoundedEngine(pk.FakeEngine):
            def save(self, cid, tokens):
                self.test.assertLessEqual(sum(pk.Parking.manifest_bytes(m) for m in self.store.values()) +
                                          self.save_size_bound(cid,tokens), 250)
                return super().save(cid,tokens)
        engine = BoundedEngine(bytes_per_token=0, floor=100); engine.test = self
        k, _, _ = keeper(engine, budget=250)
        for session in ('a','b','c'): park(k, session, turn(1))
        self.assertEqual(set(k.parked), {'b','c'}); self.assertEqual(k.total_bytes(),200)

    def test_ambiguous_save_keeps_reservation_and_blocks_repeat(self):
        class AmbiguousEngine(pk.FakeEngine):
            def save(self,cid,tokens):
                super().save(cid,tokens)
                raise OSError('lost acknowledgement')
        engine = AmbiguousEngine(bytes_per_token=0,floor=100)
        k, _, _ = keeper(engine,budget=150)
        with self.assertRaisesRegex(OSError,'lost acknowledgement'): park(k,'s',turn(1))
        self.assertEqual(k.total_bytes(),100)
        self.assertIsNone(park(k,'s',turn(1)))
        self.assertIsNone(park(k,'other',turn(2)))
        self.assertEqual(len([c for c in engine.calls if c[0]=='save']),1)
        cid = next(iter(k.retained_bytes)); k.delete(cid)
        self.assertEqual(k.total_bytes(),0)

    def test_ambiguous_old_delete_keeps_both_checkpoints_charged(self):
        class DeleteErrorEngine(pk.FakeEngine):
            fail_delete = False
            def delete(self,cid):
                if self.fail_delete: raise OSError('ambiguous delete')
                return super().delete(cid)
        engine = DeleteErrorEngine(bytes_per_token=0, floor=100)
        k, _, _ = keeper(engine,budget=250)
        old = park(k,'s',turn(1)); engine.fail_delete = True
        with self.assertRaisesRegex(OSError,'ambiguous delete'): park(k,'s',turn(1)+turn(2))
        self.assertEqual(k.total_bytes(),200)
        self.assertEqual(k.retained_bytes,{old.checkpoint_id:100})
        self.assertNotEqual(k.parked['s'].checkpoint_id,old.checkpoint_id)

    def test_exact_storage_bytes_and_underestimated_bound_fail_closed(self):
        class StoredEngine(pk.FakeEngine):
            def save(self,cid,tokens):
                manifest = super().save(cid,tokens); manifest['storage_bytes'] = 120
                return manifest
        engine = StoredEngine(bytes_per_token=0,floor=100); k, _, _ = keeper(engine,budget=250)
        with self.assertRaisesRegex(ValueError,'exceeded admitted'): park(k,'s',turn(1))
        self.assertEqual(k.total_bytes(),120)
        for value in (True, -1, '120'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pk.Parking.manifest_bytes({'storage_bytes':value,'blobs':[{'bytes':100}]})

    def test_fake_engine_is_fail_closed(self):
        eng = pk.FakeEngine()
        eng.save("c", [1, 2, 3])
        self.assertEqual(eng.restore("c", [1, 2, 3, 4]), {"restored": 3, "appended": 1})
        with self.assertRaises(ValueError):
            eng.restore("c", [1, 2, 9, 4])
        with self.assertRaises(ValueError):
            eng.restore("c", [1, 2])
        self.assertEqual(eng.delete("c"), "in_use")
        eng.release("c")
        self.assertEqual(eng.delete("c"), "ok")
        self.assertEqual(eng.delete("c"), "missing")


if __name__ == "__main__":
    unittest.main()
