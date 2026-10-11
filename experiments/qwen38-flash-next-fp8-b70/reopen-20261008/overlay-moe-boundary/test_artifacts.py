import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("moe_variant_builder", HERE / "build_patch.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class Artifacts(unittest.TestCase):
    def test_seals_match(self):
        builder.check()

    def test_production_overlay_is_unchanged(self):
        baseline = json.loads(builder.before("overlay-manifest.json"))
        self.assertEqual((builder.LANE / "overlay-manifest.json").read_bytes(), builder.before("overlay-manifest.json"))
        for rel, digest in baseline["files"].items():
            self.assertEqual(builder.sha((builder.LANE / "overlay" / rel).read_bytes()), digest, rel)

    def test_stage_requires_explicit_enable_and_fresh_external_path(self):
        with patch.dict(os.environ, {"SCREEN1B_MOE_BOUNDARY":"0"}):
            with self.assertRaisesRegex(RuntimeError, "requires SCREEN"):
                builder.stage(HERE / "forbidden")
        with patch.dict(os.environ, {"SCREEN1B_MOE_BOUNDARY":"1"}):
            with self.assertRaisesRegex(RuntimeError, "outside the repository"):
                builder.stage(HERE / "forbidden")

    def test_stage_hashes_and_patch_application_exact(self):
        with tempfile.TemporaryDirectory(prefix="moe-boundary-artifacts-") as scratch:
            scratch = Path(scratch)
            with patch.dict(os.environ, {"SCREEN1B_MOE_BOUNDARY":"1"}):
                staged = builder.stage(scratch / "staged")
            preimage = scratch / "preimage"
            preimage.mkdir()
            for rel, raw in builder.baseline().items():
                out = preimage / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(raw)
            # Ordinary patch application, no git init, branch or worktree.
            subprocess.run(["git", "apply", "--check", str(HERE / "boundary.patch")], cwd=preimage, check=True)
            subprocess.run(["git", "apply", str(HERE / "boundary.patch")], cwd=preimage, check=True)
            manifest = json.loads((HERE / "patch-manifest.json").read_text())
            for rel, pin in manifest["files"].items():
                self.assertEqual(builder.sha((preimage / rel).read_bytes()), pin["after_sha256"], rel)
                self.assertEqual((preimage / rel).read_bytes(), (staged / rel).read_bytes(), rel)
            with patch.dict(os.environ, {"SCREEN1B_MOE_BOUNDARY":"1"}):
                with self.assertRaisesRegex(RuntimeError, "fresh directory"):
                    builder.stage(staged)

    def test_overlay_parses(self):
        for path in (HERE / "copies/overlay").rglob("*.py"):
            ast.parse(path.read_text(), filename=str(path))

    def test_off_kernel_has_identical_arithmetic_ast(self):
        rel = "overlay/vllm/model_executor/layers/fused_moe/fused_moe.py"
        def kernel(raw):
            return next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == "fused_moe_kernel")
        old = kernel(builder.before(rel))
        candidate = kernel((HERE / "copies" / rel).read_bytes())
        self.assertEqual(candidate.args.args[-1].arg, "DIAGNOSTIC_BOUNDARY")
        candidate.args.args.pop()
        candidate.args.defaults.pop()
        class Off(ast.NodeTransformer):
            def visit_If(self, node):
                if isinstance(node.test, ast.Name) and node.test.id == "DIAGNOSTIC_BOUNDARY":
                    return []
                if isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not) and isinstance(node.test.operand, ast.Name) and node.test.operand.id == "DIAGNOSTIC_BOUNDARY":
                    return node.body
                return self.generic_visit(node)
        candidate = Off().visit(candidate)
        self.assertEqual(ast.dump(old, include_attributes=False), ast.dump(candidate, include_attributes=False))

    def test_on_negative_return_precedes_weight_table(self):
        tree = ast.parse((HERE / "copies/overlay/vllm/model_executor/layers/fused_moe/fused_moe.py").read_text())
        k = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fused_moe_kernel")
        negative = next(i for i,n in enumerate(k.body) if isinstance(n, ast.If) and ast.unparse(n.test) == "off_experts == -1")
        guarded = next(i for i,n in enumerate(k.body) if isinstance(n, ast.If) and ast.unparse(n.test) == "DIAGNOSTIC_BOUNDARY")
        self.assertLess(negative, guarded)
        self.assertIsInstance(k.body[negative].body[-1], ast.Return)


if __name__ == "__main__":
    unittest.main()
