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
        park(k, "s2", turn(2))                                  # over budget, but s1 is in use
        self.assertIn("s1", k.parked)
        self.assertEqual(k.status()["pending_delete"], [])     # eviction skipped it, no delete pending
        # a drop while in use: the policy forgets the session, the directory waits
        d = k.before_request("s1", turn(9))
        self.assertEqual(d.dropped, "kept: in_use")
        self.assertEqual(k.status()["pending_delete"], [a.checkpoint_id])
        eng.release(a.checkpoint_id)
        park(k, "s3", turn(3))                                  # the next pass retries the delete
        self.assertNotIn(a.checkpoint_id, eng.store)
        self.assertEqual(k.status()["pending_delete"], [])

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
