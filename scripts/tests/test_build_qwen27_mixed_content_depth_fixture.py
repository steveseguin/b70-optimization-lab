from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).parents[1] / "build-qwen27-mixed-content-depth-fixture.py"
SPEC = importlib.util.spec_from_file_location("mixed_content_fixture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert add_special_tokens is False
        offset = ord(text[0])
        return [offset + index for index in range(40000)]


class MixedContentFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / ".git").mkdir()
        self.tokenizer = self.root / "tokenizer"
        self.tokenizer.mkdir()
        (self.tokenizer / "tokenizer.json").write_text("{}\n")
        (self.tokenizer / "tokenizer_config.json").write_text("{}\n")
        self.sources = []
        for label, marker in (("prose", "a"), ("code", "b"), ("docs", "c")):
            path = self.root / f"{label}.txt"
            path.write_text(marker + " source\n", encoding="utf-8")
            self.sources.append(f"{label}={path.name}")
        self.generator = self.root / "generator.py"
        self.generator.write_text("# generator\n")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def payload(self) -> dict[str, Any]:
        return MODULE.build_payload(
            repo_root=self.root,
            tokenizer_dir=self.tokenizer,
            source_specs=self.sources,
            fixture_id="mixed-v1",
            logical_model="Qwen3.8-27B",
            tokenizer_repository="example/tokenizer",
            tokenizer_revision="revision",
            tokenizer=FakeTokenizer(),
            runtime_versions={"transformers": "test"},
            generator_path=self.generator,
        )

    def args(self, output: Path, **mode: bool) -> argparse.Namespace:
        values = {
            "repo_root": self.root,
            "tokenizer_dir": self.tokenizer,
            "source": self.sources,
            "fixture_id": "mixed-v1",
            "logical_model": "Qwen3.8-27B",
            "tokenizer_repository": "example/tokenizer",
            "tokenizer_revision": "revision",
            "output": output,
            "plan": False,
            "check": False,
            "write": False,
        }
        values.update(mode)
        return argparse.Namespace(**values)

    @staticmethod
    def loader(_path: Path) -> tuple[FakeTokenizer, dict[str, str]]:
        return FakeTokenizer(), {"transformers": "test"}

    def test_three_unrepeated_classes_at_every_depth(self) -> None:
        payload = self.payload()
        self.assertEqual(len(payload["cases"]), 18)
        self.assertTrue(payload["provenance"]["evidence"]["representative_natural_context"])
        self.assertFalse(payload["provenance"]["evidence"]["natural_task_or_retrieval_prompt"])
        self.assertFalse(payload["provenance"]["construction"]["source_repetition"])
        self.assertEqual(
            payload["provenance"]["construction"]["source_classes"],
            ["prose", "code", "docs"],
        )
        for case in payload["cases"]:
            self.assertEqual(len(case["prompt_token_ids"]), case["depth"])
            self.assertEqual(case["token_count"], case["depth"])
        self.assertEqual(
            {entry["path"] for entry in payload["provenance"]["sources"]},
            {"prose.txt", "code.txt", "docs.txt"},
        )

    def test_rejects_absolute_or_short_sources(self) -> None:
        with self.assertRaisesRegex(MODULE.ContractError, "repository-relative"):
            MODULE.build_payload(
                repo_root=self.root,
                tokenizer_dir=self.tokenizer,
                source_specs=[f"prose={self.root / 'prose.txt'}", *self.sources[1:]],
                fixture_id="mixed-v1",
                logical_model="Qwen3.8-27B",
                tokenizer_repository="example/tokenizer",
                tokenizer_revision="revision",
                tokenizer=FakeTokenizer(),
                generator_path=self.generator,
            )

        class ShortTokenizer:
            def encode(self, _text: str, *, add_special_tokens: bool) -> list[int]:
                return [1, 2, 3]

        with self.assertRaisesRegex(MODULE.ContractError, "without repetition"):
            MODULE.build_payload(
                repo_root=self.root,
                tokenizer_dir=self.tokenizer,
                source_specs=self.sources,
                fixture_id="mixed-v1",
                logical_model="Qwen3.8-27B",
                tokenizer_repository="example/tokenizer",
                tokenizer_revision="revision",
                tokenizer=ShortTokenizer(),
                generator_path=self.generator,
            )

    def test_write_is_create_only_and_check_is_exact(self) -> None:
        output = self.root / "fixture.json"
        created = MODULE.execute(self.args(output, write=True), tokenizer_loader=self.loader)
        self.assertEqual(created["status"], "created")
        original = output.read_bytes()
        checked = MODULE.execute(self.args(output, check=True), tokenizer_loader=self.loader)
        self.assertEqual(checked["status"], "passed")
        self.assertEqual(output.read_bytes(), original)
        with self.assertRaisesRegex(MODULE.ContractError, "refusing to overwrite"):
            MODULE.execute(self.args(output, write=True), tokenizer_loader=self.loader)


if __name__ == "__main__":
    unittest.main()
