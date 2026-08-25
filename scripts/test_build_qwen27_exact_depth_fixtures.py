from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).with_name("build-qwen27-exact-depth-fixtures.py")
SPEC = importlib.util.spec_from_file_location("qwen27_exact_depth_fixtures", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeTokenizer:
    bos_token_id = 101
    eos_token_id = 102

    def __init__(self, ids: list[int] | None = None) -> None:
        self.ids = [11, 12, 13] if ids is None else ids
        self.calls: list[tuple[str, bool]] = []

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        self.calls.append((text, add_special_tokens))
        return list(self.ids)


class ExactDepthFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tokenizer_dir = self.root / "qwen-tokenizer"
        self.tokenizer_dir.mkdir()
        (self.tokenizer_dir / "tokenizer.json").write_text('{"fixture":1}\n')
        (self.tokenizer_dir / "tokenizer_config.json").write_text(
            '{"model_max_length":32768}\n'
        )
        self.source = self.root / "source.txt"
        self.source.write_text("explicit fixture source\n", encoding="utf-8")
        self.generator = self.root / "generator.py"
        self.generator.write_text("# fixture generator\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def payload(
        self,
        tokenizer: FakeTokenizer | None = None,
        *,
        policy: str = "none",
        logical_model: str = "Qwen3.6-27B",
    ) -> dict[str, Any]:
        return MODULE.build_payload(
            tokenizer_dir=self.tokenizer_dir,
            source_path=self.source,
            fixture_id="qwen36-fixture-v1",
            logical_model=logical_model,
            tokenizer_revision="revision-fixture",
            special_token_policy=policy,
            tokenizer=tokenizer or FakeTokenizer(),
            runtime_versions={"transformers": "fixture"},
            generator_path=self.generator,
        )

    def args(self, output: Path, **mode: bool) -> argparse.Namespace:
        values = {
            "tokenizer_dir": self.tokenizer_dir,
            "source": self.source,
            "fixture_id": "qwen36-fixture-v1",
            "logical_model": "Qwen3.6-27B",
            "tokenizer_revision": "revision-fixture",
            "special_token_policy": "none",
            "output": output,
            "plan": False,
            "check": False,
            "write": False,
        }
        values.update(mode)
        return argparse.Namespace(**values)

    def loader(self, _path: Path) -> tuple[FakeTokenizer, dict[str, str]]:
        return FakeTokenizer(), {"transformers": "fixture"}

    def test_exact_depths_are_flat_integer_lists(self) -> None:
        tokenizer = FakeTokenizer()
        payload = self.payload(tokenizer)
        self.assertEqual(payload["depths"], list(MODULE.DEPTHS))
        self.assertEqual(payload["schema"], "openai-token-depth-fixture-v1")
        self.assertEqual(payload["fixture_id"], "qwen36-fixture-v1")
        self.assertEqual(len(payload["cases"]), len(MODULE.DEPTHS))
        for case, depth in zip(payload["cases"], MODULE.DEPTHS, strict=True):
            self.assertEqual(case["id"], f"depth-{depth}")
            self.assertEqual(case["depth"], depth)
            self.assertEqual(case["token_count"], depth)
            self.assertEqual(len(case["prompt_token_ids"]), depth)
            self.assertTrue(
                all(type(value) is int for value in case["prompt_token_ids"])
            )
        self.assertEqual(payload["cases"][0]["prompt_token_ids"], [])
        self.assertEqual(tokenizer.calls, [("explicit fixture source\n", False)])

    def test_special_token_policy_and_grade_are_explicit(self) -> None:
        payload = self.payload(policy="bos-and-eos")
        first_nonzero = payload["cases"][1]["prompt_token_ids"]
        self.assertEqual(first_nonzero[0], 101)
        self.assertEqual(first_nonzero[-1], 102)
        self.assertEqual(payload["cases"][0]["prompt_token_ids"], [])
        provenance = payload["provenance"]
        self.assertEqual(provenance["evidence"]["grade"], "C")
        self.assertFalse(provenance["evidence"]["representative_natural_context"])
        self.assertIn("repeat", provenance["construction"]["policy"])
        self.assertEqual(
            provenance["construction"]["special_token_policy"], "bos-and-eos"
        )
        self.assertEqual(
            payload["provenance_sha256"],
            MODULE.sha256_bytes(MODULE.canonical_json_bytes(provenance)),
        )

    def test_provenance_binds_source_tokenizer_generator_and_model(self) -> None:
        payload = self.payload()
        provenance = payload["provenance"]
        self.assertEqual(
            provenance["source"]["sha256"], MODULE.file_sha256(self.source)
        )
        self.assertEqual(
            provenance["generator"]["sha256"], MODULE.file_sha256(self.generator)
        )
        self.assertEqual(
            set(provenance["tokenizer"]["files_sha256"]),
            {"tokenizer.json", "tokenizer_config.json"},
        )
        self.assertEqual(provenance["tokenizer"]["logical_model"], "Qwen3.6-27B")
        q38 = self.payload(logical_model="Qwen3.8-27B")
        self.assertNotEqual(
            MODULE.canonical_json_bytes(payload), MODULE.canonical_json_bytes(q38)
        )

    def test_default_mode_is_inert_plan(self) -> None:
        output = self.root / "fixture.json"
        summary = MODULE.execute(self.args(output), tokenizer_loader=self.loader)
        self.assertEqual(summary["mode"], "plan")
        self.assertEqual(summary["status"], "planned")
        self.assertFalse(output.exists())

    def test_write_is_create_only_and_check_is_non_mutating(self) -> None:
        output = self.root / "fixture.json"
        created = MODULE.execute(
            self.args(output, write=True), tokenizer_loader=self.loader
        )
        original = output.read_bytes()
        self.assertEqual(created["status"], "created")
        with self.assertRaisesRegex(MODULE.ContractError, "refusing to overwrite"):
            MODULE.execute(self.args(output, write=True), tokenizer_loader=self.loader)
        checked = MODULE.execute(
            self.args(output, check=True), tokenizer_loader=self.loader
        )
        self.assertEqual(checked["status"], "passed")
        self.assertEqual(output.read_bytes(), original)

    def test_check_rejects_drift_without_mutation(self) -> None:
        output = self.root / "fixture.json"
        MODULE.execute(self.args(output, write=True), tokenizer_loader=self.loader)
        payload = json.loads(output.read_text())
        payload["cases"][1]["prompt_token_ids"][0] = 999
        output.write_text(json.dumps(payload), encoding="utf-8")
        drifted = output.read_bytes()
        with self.assertRaisesRegex(MODULE.ContractError, "differs"):
            MODULE.execute(self.args(output, check=True), tokenizer_loader=self.loader)
        self.assertEqual(output.read_bytes(), drifted)

    def test_rejects_empty_source_tokens_and_incomplete_tokenizer_identity(
        self,
    ) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "zero IDs"):
            self.payload(FakeTokenizer([]))
        (self.tokenizer_dir / "tokenizer.json").unlink()
        with self.assertRaisesRegex(MODULE.ContractError, "identity is incomplete"):
            self.payload()


if __name__ == "__main__":
    unittest.main()
