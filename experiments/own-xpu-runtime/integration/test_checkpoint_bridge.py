"""Replay actual packet181 device metadata; never invoke the native engine."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest

from checkpoint_bridge import BridgeRefusal, IDENTITY_FIELDS, validate_snapshot


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "checkpoint-fixtures-p181"
ROOT = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture(stem="s1"):
    payload = json.loads((FIXTURES / f"{stem}.small-payloads.json").read_text())
    return dict(
        inspect_stdout=(FIXTURES / f"{stem}.inspect.json").read_bytes(),
        inspect_returncode=0,
        manifest_bytes=(FIXTURES / f"{stem}.manifest.json").read_bytes(),
        tokens_bytes=bytes.fromhex(payload["tokens.bin"]),
        next_token_bytes=bytes.fromhex(payload["next_token.bin"]),
        checkpoint_id=stem,
        expected_identity=json.loads((FIXTURES / "historical-engine-identity.json").read_text()),
    )


def replace_manifest(args, edit):
    """Negative test of semantic checks even with a mutually consistent envelope."""
    native = json.loads(args["manifest_bytes"])
    edit(native)
    args["manifest_bytes"] = (json.dumps(native, separators=(",", ":")) + "\n").encode()
    inspected = json.loads(args["inspect_stdout"])
    inspected["manifest"] = native
    inspected["manifest_sha256"] = sha(args["manifest_bytes"])
    args["inspect_stdout"] = json.dumps(inspected).encode()


def replace_inspect(args, edit):
    inspected = json.loads(args["inspect_stdout"])
    edit(inspected)
    args["inspect_stdout"] = json.dumps(inspected).encode()


class CheckpointBridgeTests(unittest.TestCase):
    def postreply_envelope(self):
        """Synthetic contract-policy case, not p198 native/device evidence."""
        args = fixture()
        def edit(native):
            native['contract'] = 'v1.2+p198'
            native['label'] = 'experimental-postreply-front'
            native['engine']['binary_sha256'] = 'b' * 64
            native['qualified_by']['device_gates'] = []
        replace_manifest(args, edit)
        native = json.loads(args['manifest_bytes'])
        replace_inspect(args, lambda inspected: inspected.update(
            contract=native['contract'], label=native['label']))
        args['expected_identity'] = {k:native[k] for k in IDENTITY_FIELDS}
        return args

    def test_postreply_contract_requires_explicit_selection_and_keeps_label(self):
        args = self.postreply_envelope()
        with self.assertRaisesRegex(BridgeRefusal, 'unsupported checkpoint contract'):
            validate_snapshot(**args)
        view = validate_snapshot(**args, admitted_contract='v1.2+p198')
        self.assertEqual(view.manifest_bytes, args['manifest_bytes'])
        self.assertEqual(view.parking_metadata()['label'], 'experimental-postreply-front')
        self.assertEqual(view.parking_metadata()['contract'], 'v1.2+p198')

    def test_explicit_postreply_selection_does_not_bypass_binary_identity(self):
        args = self.postreply_envelope()
        args['expected_identity']['engine'] = copy.deepcopy(args['expected_identity']['engine'])
        args['expected_identity']['engine']['binary_sha256'] = 'c' * 64
        with self.assertRaisesRegex(BridgeRefusal, 'engine identity differs'):
            validate_snapshot(**args, admitted_contract='v1.2+p198')

    def test_unknown_contract_cannot_be_enabled_by_expected_identity(self):
        for contract in ('v1.2+p197','future',None):
            with self.subTest(contract=contract), self.assertRaisesRegex(BridgeRefusal, 'unsupported admitted'):
                validate_snapshot(**fixture(), admitted_contract=contract)

    def test_fixture_provenance_and_binary_payloads(self):
        provenance = json.loads((FIXTURES / "provenance.json").read_text())
        for name, digest in provenance["files_sha256"].items():
            self.assertEqual(sha((FIXTURES / name).read_bytes()), digest, name)
        for row in provenance["sources"]:
            if row["encoding"] == "verbatim":
                self.assertEqual(sha((FIXTURES / row["fixture"]).read_bytes()), row["source_sha256"])
            elif "field" in row:
                data = bytes.fromhex(json.loads((FIXTURES / row["fixture"]).read_text())[row["field"]])
                self.assertEqual(len(data), row["bytes"])
                self.assertEqual(sha(data), row["source_sha256"])
        native = json.loads((FIXTURES / "s1.manifest.json").read_text())
        self.assertEqual(fixture()["expected_identity"], {k: native[k] for k in IDENTITY_FIELDS})

    def test_real_metadata_snapshot_and_actual_append(self):
        args = fixture()
        view = validate_snapshot(**args)
        self.assertEqual((len(view.processed_tokens), view.pending_token), (342, 37574))
        self.assertEqual(view.processed_tokens[-2:], (43164, 22843))
        self.assertEqual(view.native_inspect_mode, "metadata")
        self.assertEqual(view.manifest_sha256, "0974a0e560e815d790ff622b7249038a85a5ddd9ceb088534d99d72a19362d93")
        tokens = tuple(map(int, (FIXTURES / "s1.append-input.txt").read_text().split()))
        plan = view.plan_append(tokens, max_new=128)
        self.assertEqual((len(tokens), plan.processed_tokens, plan.saved_history_tokens), (469, 342, 343))
        self.assertEqual((plan.delta_tokens, plan.native_prefill_tokens), (126, 127))
        self.assertEqual(plan.input_tokens, tokens)
        self.assertEqual(view.manifest_bytes, args["manifest_bytes"])

    def test_real_full_inspect_snapshot(self):
        view = validate_snapshot(**fixture("s2"))
        self.assertEqual((len(view.processed_tokens), view.pending_token), (596, 11))
        self.assertEqual(view.native_inspect_mode, "full")
        self.assertEqual(view.plan_append(view.saved_history, max_new=64).native_prefill_tokens, 1)

    def test_policy_projection_matches_existing_parking_hash(self):
        # Import existing policy read-only. Its Engine/backend remains unmodified.
        import sys
        spec = importlib.util.spec_from_file_location("bridge_test_parking", ROOT / "tools/ctxkeeper/parking.py")
        policy = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = policy
        try:
            spec.loader.exec_module(policy)
            args = fixture()
            view = validate_snapshot(**args)
            projected = view.parking_metadata()
            native = json.loads(args["manifest_bytes"])
            self.assertEqual(projected["token_state"]["length"], 343)
            self.assertEqual(projected["token_state"]["tokens_sha256"], policy.prefix_hash(view.saved_history))
            self.assertNotEqual(projected["token_state"]["tokens_sha256"], native["token_state"]["tokens_sha256"])
            for key in ("label", "contract", "model", "engine", "blobs"):
                self.assertEqual(projected[key], native[key])
            self.assertFalse(projected["bridge"]["full_state_revalidated_by_bridge"])

            class ReadOnlyEngine:
                def identity(self):
                    return {"model": native["model"]["identity_tsv_sha256"], "engine": native["engine"]["binary_sha256"]}

                def inspect(self, checkpoint_id):
                    assert checkpoint_id == "s1"
                    return view.parking_metadata()

                def delete(self, checkpoint_id):
                    return "ok"

            parking = policy.Parking(ReadOnlyEngine(), lambda messages: "", lambda text: list(view.saved_history) + [42], budget_bytes=100_000_000)
            parking.parked["session"] = policy.Parked("s1", 343, 68756516, 0)
            decision = parking.before_request("session", [])
            self.assertEqual((decision.action, decision.saved_tokens, decision.delta_tokens), ("restore", 343, 1))
            wrong_pending = list(view.saved_history)
            wrong_pending[-1] += 1
            parking.tokenize = lambda text: wrong_pending + [42]
            self.assertEqual(parking.before_request("session", []).action, "prefill")
        finally:
            sys.modules.pop(spec.name, None)

    def test_native_inspect_failures_are_not_hits(self):
        edits = [
            lambda a: a.update(inspect_returncode=1),
            lambda a: a.update(inspect_returncode=True),
            lambda a: replace_inspect(a, lambda x: x.update(ok=False)),
            lambda a: replace_inspect(a, lambda x: x.update(error={"check": "lock"})),
            lambda a: replace_inspect(a, lambda x: x.update(device_required=True)),
            lambda a: replace_inspect(a, lambda x: x.update(mode="other")),
            lambda a: replace_inspect(a, lambda x: x.update(checkpoint_id="s2")),
            lambda a: replace_inspect(a, lambda x: x.update(label="experimental")),
            lambda a: replace_inspect(a, lambda x: x["verified"].update(fields_tsv_cross_check=False)),
            lambda a: replace_inspect(a, lambda x: x["verified"].update(tokens=True)),
        ]
        for edit in edits:
            args = fixture()
            edit(args)
            with self.subTest(edit=edits.index(edit)), self.assertRaises(BridgeRefusal):
                validate_snapshot(**args)

    def test_every_running_identity_field_must_match(self):
        for key in IDENTITY_FIELDS:
            args = fixture()
            args["expected_identity"][key] = "changed"
            with self.subTest(key=key), self.assertRaisesRegex(BridgeRefusal, key + " identity differs"):
                validate_snapshot(**args)
        args = fixture()
        del args["expected_identity"]["tokenizer_identity"]
        with self.assertRaises(BridgeRefusal):
            validate_snapshot(**args)

    def test_changed_manifest_bytes_or_embedded_manifest_refused(self):
        args = fixture()
        args["manifest_bytes"] += b" "
        with self.assertRaisesRegex(BridgeRefusal, "manifest hash"):
            validate_snapshot(**args)
        args = fixture()
        replace_inspect(args, lambda x: x["manifest"]["token_state"].update(next_token=1))
        with self.assertRaisesRegex(BridgeRefusal, "inspect manifest"):
            validate_snapshot(**args)

    def test_corrupt_truncated_and_wrong_endian_tokens_refused(self):
        for mutation in (
            lambda data: data[:-4],
            lambda data: bytes([data[0] ^ 1]) + data[1:],
            lambda data: b"".join(data[i:i+4][::-1] for i in range(0, len(data), 4)),
        ):
            args = fixture()
            args["tokens_bytes"] = mutation(args["tokens_bytes"])
            with self.subTest(mutation=mutation), self.assertRaises(BridgeRefusal):
                validate_snapshot(**args)

    def test_out_of_range_saved_token_even_with_updated_digest_refused(self):
        args = fixture()
        args["tokens_bytes"] = struct.pack("<i", -1) + args["tokens_bytes"][4:]
        replace_manifest(args, lambda x: x["token_state"].update(tokens_sha256=sha(args["tokens_bytes"])))
        with self.assertRaisesRegex(BridgeRefusal, "saved token outside"):
            validate_snapshot(**args)

    def test_token_state_semantic_edits_refused(self):
        for updates in (
            {"length": 343}, {"position": 341}, {"position": True}, {"prompt_length": 343},
            {"next_token": -1}, {"next_token": 37575}, {"token_history": [22843, 43164]},
            {"tokens_sha256": "0" * 64},
        ):
            args = fixture()
            replace_manifest(args, lambda x: x["token_state"].update(updates))
            with self.subTest(updates=updates), self.assertRaises(BridgeRefusal):
                validate_snapshot(**args)

    def test_pending_control_and_inventory_edits_refused(self):
        args = fixture()
        args["next_token_bytes"] = struct.pack("<i", 37575)
        with self.assertRaisesRegex(BridgeRefusal, "pending token control"):
            validate_snapshot(**args)
        for edit in (
            lambda x: x["blobs"].append(copy.deepcopy(x["blobs"][0])),
            lambda x: x.update(blobs=[b for b in x["blobs"] if b["name"] != "next_token"]),
            lambda x: next(b for b in x["blobs"] if b["name"] == "next_token").update(sha256="0" * 64),
            lambda x: x["measurements"].update(save_bytes=0),
        ):
            args = fixture()
            replace_manifest(args, edit)
            with self.subTest(edit=edit), self.assertRaises(BridgeRefusal):
                validate_snapshot(**args)

    def test_full_inspect_incomplete_verification_refused(self):
        for key, value in (("tokens", None), ("semantic_blob_checks", None), ("blobs_verified", 127), ("blob_bytes_verified", 0)):
            args = fixture("s2")
            replace_inspect(args, lambda x: x["verified"].update({key: value}))
            with self.subTest(key=key), self.assertRaises(BridgeRefusal):
                validate_snapshot(**args)

    def test_prefix_pending_and_context_boundaries(self):
        view = validate_snapshot(**fixture())
        saved = list(view.saved_history)
        wrong_prefix = saved.copy()
        wrong_prefix[10] += 1
        wrong_pending = saved.copy()
        wrong_pending[-1] += 1
        cases = (
            (saved[:-1], 1), (wrong_prefix, 1), (wrong_pending, 1),
            (saved + [-1], 1), (saved + [view.vocab], 1), (saved + [True], 1),
            (saved, 0), (saved, True), (saved, view.context),
        )
        for tokens, maximum in cases:
            with self.subTest(tokens=len(tokens), max_new=maximum), self.assertRaises(BridgeRefusal):
                view.plan_append(tokens, max_new=maximum)
        empty_delta = view.plan_append(saved, max_new=512)
        self.assertEqual(empty_delta.delta_tokens, 0)
        self.assertEqual(empty_delta.native_prefill_tokens, 1)
        with self.assertRaises(BridgeRefusal):
            view.plan_append(saved, max_new=513)
        filled = saved + [42] * (view.context - 512 - len(saved))
        exact = view.plan_append(filled, max_new=512)
        self.assertEqual(len(exact.input_tokens) + exact.max_new, view.context)
        with self.assertRaises(BridgeRefusal):
            view.plan_append(filled + [42], max_new=512)

    def test_native_checkpoint_id_boundaries(self):
        for checkpoint_id, accepted in (("a", True), ("a" * 64, True), ("a" * 65, False),
                                        ("a.lock", False), (".hidden", False), ("a/b", False),
                                        ("", False), ("é", False)):
            args = fixture()
            args["checkpoint_id"] = checkpoint_id
            replace_manifest(args, lambda x: x.update(checkpoint_id=checkpoint_id))
            replace_inspect(args, lambda x: x.update(checkpoint_id=checkpoint_id))
            with self.subTest(checkpoint_id=checkpoint_id):
                if accepted:
                    self.assertEqual(validate_snapshot(**args).checkpoint_id, checkpoint_id)
                else:
                    with self.assertRaisesRegex(BridgeRefusal, "invalid checkpoint id"):
                        validate_snapshot(**args)

    def test_successor_contract_needs_explicit_bridge_extension(self):
        args = fixture()
        replace_manifest(args, lambda x: x.update(contract="v1.2+p197", label="experimental-warm-front"))
        replace_inspect(args, lambda x: x.update(contract="v1.2+p197", label="experimental-warm-front"))
        args["expected_identity"].update(contract="v1.2+p197", label="experimental-warm-front")
        with self.assertRaisesRegex(BridgeRefusal, "unsupported checkpoint contract/label"):
            validate_snapshot(**args)

    def test_duplicate_keys_malformed_and_missing_fields_refused(self):
        for payload in (b'[]', b'{"ok":true,"ok":true}', b'{"value":NaN}', b'{', b'{}'):
            args = fixture()
            args["inspect_stdout"] = payload
            with self.subTest(payload=payload), self.assertRaises(BridgeRefusal):
                validate_snapshot(**args)

    def test_projection_mutation_does_not_change_validated_snapshot(self):
        view = validate_snapshot(**fixture())
        first = view.parking_metadata()
        first["token_state"]["length"] = 0
        first["engine"]["binary_sha256"] = "0" * 64
        second = view.parking_metadata()
        self.assertEqual(second["token_state"]["length"], 343)
        self.assertNotEqual(second["engine"]["binary_sha256"], "0" * 64)


if __name__ == "__main__":
    unittest.main()
