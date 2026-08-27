#!/usr/bin/env python3
"""Static regressions for measured OPT workload binding and withholding."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "learn/assets/mlbottleneck-bridge.js"
BUILD_MODEL_PAGES = ROOT / "tools/build-model-pages.py"
PACKAGE_CATALOG = ROOT / "packages/catalog.json"
FAMILY_CATALOG = ROOT / "families/catalog.json"

# Each pinned pair is the packet's own recorded workload convention: the
# conventional first-hundred-words suites run ~128-token prompts with
# 100-128-token answers. MiniMax records a longer shape. The FP8 TP2 packet is
# deliberately absent because its promoted result changes speculative depth
# with active-request count and has no configuration-exact projection preset.
PINNED_WORKLOADS = {
    "gemma4-26b-a4b-q8-b70-125tps-20260701": (128, 128),
    "laguna-s-2.1-int4-b70-125tps-20260731": (128, 128),
    "lfm25-26b-q8-b70": (128, 128),
    "minimax-m27-b70-89tps-20260520": (512, 1536),
    "muse-glimmer-30b-q8-woq-b70-100tps-20260813": (128, 128),
    "nemotron-35-lightning-30b-a3b-b70": (128, 100),
    "ornith-15-35b-a3b-q4km-b70": (128, 100),
    "ornith-15-9b-q8-b70": (128, 100),
    "qwen38-27b-q4km-tp1-b70": (128, 128),
    "qwen38-27b-q4km-tp2-asrock-b70": (128, 128),
}


def load_build_model_pages():
    spec = importlib.util.spec_from_file_location(
        "build_model_pages_opt_contract", BUILD_MODEL_PAGES
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def javascript_function(source: str, name: str) -> str:
    """Extract one ordinary JavaScript function with balanced braces."""

    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\(", source)
    if not match:
        raise AssertionError(f"missing JavaScript function {name}")
    start = source.find("{", match.end())
    if start < 0:
        raise AssertionError(f"missing body for JavaScript function {name}")

    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(source)):
        character = source[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"', "`"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    raise AssertionError(f"unterminated JavaScript function {name}")


class MeasuredOptContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_build_model_pages()
        cls.packages = json.loads(PACKAGE_CATALOG.read_text(encoding="utf-8"))[
            "packages"
        ]
        cls.packages_by_id = {package["id"]: package for package in cls.packages}

        family_catalog = json.loads(FAMILY_CATALOG.read_text(encoding="utf-8"))
        cls.family_packets = {}
        for entry in family_catalog["families"]:
            family = json.loads(
                (ROOT / entry["manifest"]).read_text(encoding="utf-8")
            )
            for packet in family.get("packets") or []:
                packet_id = packet["id"]
                if packet_id in cls.family_packets:
                    raise AssertionError(f"duplicate family packet {packet_id}")
                cls.family_packets[packet_id] = packet

    def test_bridge_rejects_missing_or_nonpositive_workload_lengths(self) -> None:
        source = BRIDGE.read_text(encoding="utf-8")
        function = javascript_function(source, "requestFromDataset")
        compact = re.sub(r"\s+", " ", function)

        self.assertIn("Number(data.mlPrompt)", function)
        self.assertIn("Number(data.mlOutput)", function)
        guard = re.search(
            r"\bif\s*\((?P<condition>.*?)\)\s*(?:\{\s*)?return null", compact
        )
        self.assertIsNotNone(guard, "invalid workload selectors must return null")
        condition = guard.group("condition")
        for variable in ("promptTokens", "outputTokens"):
            with self.subTest(variable=variable):
                self.assertRegex(
                    condition,
                    rf"!Number\.isInteger\({variable}\)\s*\|\|\s*"
                    rf"{variable}\s*<=\s*0",
                )
        self.assertNotRegex(function, r"\b(?:1024|256)\b")

    def test_only_exact_measured_workloads_enable_detail_projections(self) -> None:
        mapping = self.builder.PACKAGE_ML
        configured = {}
        for package_id, request in mapping.items():
            prompt_present = "prompt_tokens" in request
            output_present = "output_tokens" in request
            with self.subTest(package_id=package_id):
                self.assertEqual(
                    prompt_present,
                    output_present,
                    "a partial workload selector must fail closed",
                )
                if prompt_present:
                    self.assertIs(type(request["prompt_tokens"]), int)
                    self.assertIs(type(request["output_tokens"]), int)
                    self.assertGreater(request["prompt_tokens"], 0)
                    self.assertGreater(request["output_tokens"], 0)
                    configured[package_id] = (
                        request["prompt_tokens"],
                        request["output_tokens"],
                    )
        self.assertEqual(configured, PINNED_WORKLOADS)

    def test_family_packet_projections_match_detail_mappings(self) -> None:
        for package_id, request in self.builder.PACKAGE_ML.items():
            with self.subTest(package_id=package_id):
                self.assertIn(package_id, self.family_packets)
                self.assertEqual(
                    self.family_packets[package_id].get("projection"), request
                )

    def test_dynamic_mtp_packet_has_no_mtp0_projection(self) -> None:
        package_id = "qwen38-27b-fp8-vllm-tp2-asrock-b70"
        self.assertNotIn(package_id, self.builder.PACKAGE_ML)
        self.assertNotIn("projection", self.family_packets[package_id])

    def test_unpinned_mapped_detail_pages_are_static_withheld(self) -> None:
        mapping = self.builder.PACKAGE_ML
        self.assertLessEqual(set(mapping), set(self.packages_by_id))

        for package_id, request in mapping.items():
            package = self.packages_by_id[package_id]
            rendered = self.builder.page(package, self.packages)
            with self.subTest(package_id=package_id):
                if package_id in PINNED_WORKLOADS:
                    prompt, output = PINNED_WORKLOADS[package_id]
                    self.assertIn(f'data-ml-prompt="{prompt}"', rendered)
                    self.assertIn(f'data-ml-output="{output}"', rendered)
                    self.assertIn('id="package-projection"', rendered)
                    self.assertNotIn("OPT —", rendered)
                    self.assertNotIn(
                        "like-for-like tuned-run projection is withheld", rendered
                    )
                else:
                    self.assertNotIn("prompt_tokens", request)
                    self.assertNotIn("output_tokens", request)
                    self.assertNotIn("data-ml-prompt=", rendered)
                    self.assertNotIn("data-ml-output=", rendered)
                    self.assertNotIn('id="package-projection"', rendered)
                    self.assertIn("OPT —", rendered)
                    self.assertIn(
                        "like-for-like tuned-run projection is withheld", rendered
                    )


if __name__ == "__main__":
    unittest.main()
