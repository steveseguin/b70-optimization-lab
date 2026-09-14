#!/usr/bin/env python3
"""CPU-only, pinned-source tests for the unapplied LTX encoder candidates.

Extracts actual upstream methods, applies the tracked patches in memory, and
uses synthetic CPU tensors or explicitly fake device modules. Never imports
ComfyUI, loads weights, changes the source checkout, or initializes a GPU.
These tests are not full-model numerical or production lifecycle qualification.
"""

import argparse
import ast
import contextlib
import hashlib
import json
import logging
from pathlib import Path
import re
import subprocess
import types
import unittest

import torch


PIN = "19e1058f4c445ef74047e77a23f9ca7684c1e4b6"
LANE = Path(__file__).resolve().parents[1]
SOURCE = Path("/home/steve/src/ComfyUI-ltx25-baseline")
PATCH_NAMES = ("encoder-crop-before-cpu.patch", "encoder-resident-accounting.patch")
SOURCES = ("comfy/sd1_clip.py", "comfy/text_encoders/lt.py", "comfy/model_patcher.py")
ORIGINAL = {}
CANDIDATE = {}


def apply_patch_in_memory(sources, patch):
    """Apply this lane's ordinary unified diffs with exact context checks."""
    result = sources.copy()
    lines = patch.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        if not lines[index].startswith("--- a/"):
            raise ValueError(f"Unexpected patch header: {lines[index]!r}")
        name = lines[index][6:].rstrip("\n")
        if lines[index + 1] != f"+++ b/{name}\n":
            raise ValueError("Only same-path source patches are supported")
        source_lines = result[name].splitlines(keepends=True)
        output = []
        cursor = 0
        index += 2
        while index < len(lines) and lines[index].startswith("@@ "):
            match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*\n", lines[index])
            if not match:
                raise ValueError("Invalid hunk")
            start = int(match[1]) - 1
            if start < cursor:
                raise ValueError("Overlapping hunks")
            output.extend(source_lines[cursor:start])
            cursor = start
            old_count = new_count = 0
            index += 1
            while index < len(lines) and not lines[index].startswith(("@@ ", "--- a/")):
                marker, content = lines[index][0], lines[index][1:]
                if marker in (" ", "-"):
                    if cursor >= len(source_lines) or source_lines[cursor] != content:
                        raise ValueError(f"Patch context mismatch in {name}:{cursor + 1}")
                    cursor += 1
                    old_count += 1
                if marker in (" ", "+"):
                    output.append(content)
                    new_count += 1
                if marker not in (" ", "+", "-"):
                    raise ValueError("Unsupported patch line")
                index += 1
            if old_count != int(match[2] or 1) or new_count != int(match[4] or 1):
                raise ValueError("Hunk count mismatch")
        output.extend(source_lines[cursor:])
        result[name] = "".join(output)
    return result


def extract(source, class_name, namespace, method=None):
    klass = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == class_name)
    node = klass if method is None else next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == method)
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, f"pinned:{class_name}:{method or 'class'}", "exec"), namespace)
    return namespace[class_name if method is None else method]


def token_encoder(source):
    return extract(source, "ClipTokenWeightEncoder", {
        "torch": torch,
        "model_management": types.SimpleNamespace(intermediate_device=lambda: torch.device("cpu")),
        "gen_empty_tokens": lambda special, length: [0] * length,
    })


class CropTests(unittest.TestCase):
    def compare_case(self, sections, valid):
        count = max(sections, 1)
        values = torch.arange(count * 4 * 8 * 6, dtype=torch.float32).reshape(count, 4, 8, 6)
        mask = torch.zeros(count, 8, dtype=torch.long)
        if valid:
            mask[:, -valid:] = 1
        inputs = [[(0, 1.0)] * 8 for _ in range(sections)]
        old = token_encoder(ORIGINAL["comfy/sd1_clip.py"])()
        new = token_encoder(CANDIDATE["comfy/sd1_clip.py"])()
        for obj in (old, new):
            obj.special_tokens = {}
            obj.encode = lambda tokens: (values.clone(), None, {"attention_mask": mask.clone()})
        reference = old.encode_token_weights(inputs)
        candidate = new.encode_token_weights(inputs, crop_to_attention_mask=True)
        valid_total = int(reference[2]["attention_mask"].sum().item())
        expected = reference[0][:, :, -valid_total:]
        self.assertTrue(torch.equal(expected, candidate[0]))
        self.assertTrue(torch.equal(reference[2]["attention_mask"], candidate[2]["attention_mask"]))
        self.assertIsNone(candidate[1])
        default = new.encode_token_weights(inputs)
        self.assertTrue(torch.equal(reference[0], default[0]))
        self.assertEqual(reference[0].dtype, candidate[0].dtype)

    def test_short_prompt(self):
        self.compare_case(1, 3)

    def test_full_prompt(self):
        self.compare_case(1, 8)

    def test_zero_mask_preserves_negative_zero_slice(self):
        self.compare_case(1, 0)

    def test_two_sections(self):
        self.compare_case(2, 5)

    def test_empty_sections(self):
        self.compare_case(0, 0)

    def test_ltx_call_enables_opt_in(self):
        tree = ast.parse(CANDIDATE["comfy/text_encoders/lt.py"])
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "encode_token_weights"
                 and any(k.arg == "crop_to_attention_mask" and isinstance(k.value, ast.Constant)
                         and k.value.value is True for k in n.keywords)]
        self.assertEqual(len(calls), 1)


class FakeModule:
    def __init__(self):
        self.comfy_cast_weights = False
        self.device = "cpu"

    def to(self, device):
        self.device = device


def wipe_fake_lowvram(module):
    if hasattr(module, "prev_comfy_cast_weights"):
        module.comfy_cast_weights = module.prev_comfy_cast_weights
        del module.prev_comfy_cast_weights


class AccountingFixture:
    """Each fake leaf is 45 units. All device movement is a string assignment."""
    def __init__(self, source):
        self.modules = [FakeModule() for _ in range(4)]
        namespace = {
            "comfy": types.SimpleNamespace(model_management=types.SimpleNamespace(
                NUM_STREAMS=0, is_device_cuda=lambda device: False)),
            "logging": logging,
            "move_weight_functions": lambda *args: 0,
            "wipe_lowvram_weight": wipe_fake_lowvram,
            "CallbacksMP": types.SimpleNamespace(ON_LOAD=0),
        }
        self.load_method = extract(source, "ModelPatcher", namespace, "load")
        self.unload_method = extract(source, "ModelPatcher", namespace, "partially_unload")
        self.patcher = types.SimpleNamespace(
            use_ejected=lambda: contextlib.nullcontext(), unpatch_hooks=lambda: None,
            _load_list=lambda: [(45, 45, str(i), m, {}) for i, m in enumerate(self.modules)],
            force_cast_weights=False, patches={}, weight_wrapper_patches={}, backup={},
            model=types.SimpleNamespace(lowvram_patch_counter=0, device="cpu"),
            patches_uuid="same", get_all_callbacks=lambda key: [],
            pin_weight_to_device=lambda key: None, apply_hooks=lambda *a, **kw: None,
            forced_hooks=None,
        )

    def load(self, budget, device="fakegpu"):
        self.load_method(self.patcher, device, lowvram_model_memory=budget)
        return self.reported, self.actual(device)

    @property
    def reported(self):
        return self.patcher.model.model_loaded_weight_memory

    def actual(self, device="fakegpu"):
        return sum(m.device == device for m in self.modules) * 45


class AccountingTests(unittest.TestCase):
    def test_original_reproduces_counter_drift(self):
        fixture = AccountingFixture(ORIGINAL["comfy/model_patcher.py"])
        rows = [fixture.load(145)]
        for _ in range(3):
            rows.append(fixture.load(fixture.reported + 0.1))
        self.assertEqual(rows, [(90, 90), (45, 90), (0, 90), (0, 90)])

    def test_candidate_preserves_reported_physical_match(self):
        fixture = AccountingFixture(CANDIDATE["comfy/model_patcher.py"])
        self.assertEqual(fixture.load(145), (90, 90))
        for _ in range(3):
            self.assertEqual(fixture.load(fixture.reported + 0.1), (90, 90))

    def test_explicit_partial_unload_still_releases_module(self):
        fixture = AccountingFixture(CANDIDATE["comfy/model_patcher.py"])
        self.assertEqual(fixture.load(145), (90, 90))
        freed = fixture.unload_method(fixture.patcher, "cpu", memory_to_free=44)
        self.assertEqual(freed, 45)
        self.assertEqual((fixture.reported, fixture.actual()), (45, 45))
        self.assertEqual(fixture.load(fixture.reported + 0.1), (45, 45))

    def test_larger_budget_loads_more_weights(self):
        fixture = AccountingFixture(CANDIDATE["comfy/model_patcher.py"])
        self.assertEqual(fixture.load(145), (90, 90))
        self.assertEqual(fixture.load(226), (180, 180))

    def test_changed_device_does_not_get_same_device_exemption(self):
        fixture = AccountingFixture(CANDIDATE["comfy/model_patcher.py"])
        self.assertEqual(fixture.load(145), (90, 90))
        self.assertEqual(fixture.load(90.1, "otherfakegpu"), (45, 45))
        # This is a branch guard test, not an endorsement of retargeting a
        # partially loaded ModelPatcher: upstream leaves the other module
        # on the previous fake device in this deliberately minimal fixture.
        self.assertEqual(fixture.actual("fakegpu"), 45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args()
    for name in SOURCES:
        ORIGINAL[name] = subprocess.check_output(
            ["git", "-C", str(args.source), "show", f"{PIN}:{name}"], text=True)
    CANDIDATE.update(ORIGINAL)
    patch_hashes = {}
    for name in PATCH_NAMES:
        path = LANE / "patches" / name
        patch_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        CANDIDATE.update(apply_patch_in_memory(CANDIDATE, path.read_text()))
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(CropTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(AccountingTests),
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"source_commit": PIN, "patch_sha256": patch_hashes,
                      "tests_run": result.testsRun, "passed": result.wasSuccessful(),
                      "evidence_scope": "CPU tensors and fake-device method emulation; no GPU"}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
