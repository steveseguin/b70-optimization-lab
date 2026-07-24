#!/usr/bin/env python3
"""CPU-only tests for the textual Laguna gather-sharded SPIR-V inspector."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import inspect_laguna_m8_gather_sharded_spirv as inspector


def module(*, fused: bool = False, fast_math: str = "NotNaN|NSZ") -> str:
    candidate = inspector.CANDIDATE
    incumbent = inspector.INCUMBENT
    fma = "%fma = OpFusedMulAdd %float %mul %acc %weight\n" if fused else ""
    return f'''OpEntryPoint Kernel %candidate_wrapper "{candidate}"
OpEntryPoint Kernel %incumbent_wrapper "{incumbent}"
OpExecutionMode %candidate_wrapper LocalSize 64 1 1
OpExecutionMode %incumbent_wrapper LocalSize 64 1 1
OpExecutionMode %candidate_wrapper ContractionOff
OpExecutionMode %incumbent_wrapper ContractionOff
OpName %candidate_impl "{candidate}"
OpName %incumbent_impl "{incumbent}"
OpName %to_float "ConvertBF16ToFloat"
OpName %from_float "ConvertFloatToBF16"
OpDecorate %mul FPFastMathMode {fast_math}
OpDecorate %add FPFastMathMode {fast_math}
OpDecorate %imul FPFastMathMode {fast_math}
OpDecorate %iadd FPFastMathMode {fast_math}
%bound10 = OpConstant %uint 10
%bound8 = OpConstant %uint 8
%candidate_wrapper = OpFunction %void None %fn
%candidate_call = OpFunctionCall %void %candidate_impl
OpFunctionEnd
%incumbent_wrapper = OpFunction %void None %fn
%incumbent_call = OpFunctionCall %void %incumbent_impl
OpFunctionEnd
%candidate_impl = OpFunction %void None %fn
%c10a = OpULessThan %bool %i %bound10
%c10b = OpULessThan %bool %i %bound10
%c8a = OpULessThan %bool %j %bound8
%c8b = OpULessThan %bool %j %bound8
%c8c = OpULessThan %bool %j %bound8
%acc = OpLoad %float %ptr
%converted = OpFunctionCall %float %to_float %bf
%mul = OpFMul %float %converted %weight
%add = OpFAdd %float %acc %mul
OpStore %ptr %add
%out = OpFunctionCall %bf16 %from_float %add
{fma}OpFunctionEnd
%incumbent_impl = OpFunction %void None %fn
%i10a = OpULessThan %bool %i %bound10
%i10b = OpULessThan %bool %i %bound10
%i10c = OpULessThan %bool %i %bound10
%i8a = OpULessThan %bool %j %bound8
%i8b = OpULessThan %bool %k %bound8
%i8c = OpULessThan %bool %k %bound8
%iacc = OpLoad %float %iptr
%iconverted = OpFunctionCall %float %to_float %ibf
%imul = OpFMul %float %iconverted %iweight
%iadd = OpFAdd %float %iacc %imul
OpStore %iptr %iadd
%iout = OpFunctionCall %bf16 %from_float %iadd
OpFunctionEnd
'''


class InspectLagunaM8GatherShardedSpirvTests(unittest.TestCase):
    def test_valid_text_passes_every_required_check(self) -> None:
        report = inspector.inspect_text(module())
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["kernels"]["candidate"]["entry_wrapper_id"], "%candidate_wrapper")
        self.assertEqual(report["kernels"]["candidate"]["implementation_id"], "%candidate_impl")
        self.assertEqual(report["kernels"]["candidate"]["loop_bounds"], {"10": 2, "8": 3})
        self.assertEqual(report["kernels"]["incumbent"]["loop_bounds"], {"10": 3, "8": 3})

    def test_fused_opcode_fails_closed(self) -> None:
        report = inspector.inspect_text(module(fused=True))
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["no_fma_or_fused_opcode"])

    def test_missing_contraction_off_fails_closed(self) -> None:
        report = inspector.inspect_text(module().replace(" ContractionOff\n", "\n"))
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["contraction_off_execution_mode"])

    def test_wrapper_must_call_its_named_implementation_once(self) -> None:
        corrupted = module().replace(
            "%candidate_call = OpFunctionCall %void %candidate_impl",
            "%candidate_call = OpFunctionCall %void %incumbent_impl",
        )
        report = inspector.inspect_text(corrupted)
        self.assertFalse(report["passed"])
        self.assertFalse(
            report["checks"]["entry_wrapper_calls_named_implementation_once"]
        )

    def test_extra_floating_point_arithmetic_fails_closed(self) -> None:
        corrupted = module().replace(
            "%out = OpFunctionCall %bf16 %from_float %add",
            "%extra = OpFMul %float %converted %weight\n"
            "%extra_add = OpFAdd %float %acc %extra\n"
            "%out = OpFunctionCall %bf16 %from_float %add",
            1,
        )
        report = inspector.inspect_text(corrupted)
        self.assertFalse(report["passed"])
        self.assertFalse(
            report["checks"]["exactly_one_fmul_and_one_fadd_per_implementation"]
        )

    def test_missing_fast_math_decoration_fails_closed(self) -> None:
        corrupted = module().replace("OpDecorate %mul FPFastMathMode NotNaN|NSZ\n", "")
        report = inspector.inspect_text(corrupted)
        self.assertFalse(report["passed"])
        self.assertFalse(
            report["checks"]["all_mul_add_fast_math_decorations_present"]
        )

    def test_missing_exact_entrypoint_is_an_error(self) -> None:
        with self.assertRaisesRegex(inspector.EvidenceError, "missing exact entry"):
            inspector.inspect_text(module().replace(inspector.CANDIDATE, "nearby_symbol"))

    def test_cli_binds_equal_bitcodes_and_writes_deterministic_json(self) -> None:
        script = Path(inspector.__file__)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spirv = root / "input.spvasm"
            built = root / "built.bc"
            saved = root / "saved.bc"
            output = root / "report.json"
            spirv.write_text(module(), encoding="utf-8")
            built.write_bytes(b"same bitcode")
            saved.write_bytes(b"same bitcode")
            completed = subprocess.run(
                ["python3", str(script), str(spirv), "--built-object", str(built), "--save-temp-bitcode", str(saved), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["passed"])
            self.assertIn("bound_bitcode_sha256", report)


    def test_cli_rejects_mismatched_bitcodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spirv = root / "input.spvasm"
            built = root / "built.bc"
            saved = root / "saved.bc"
            spirv.write_text(module(), encoding="utf-8")
            built.write_bytes(b"built")
            saved.write_bytes(b"saved")
            completed = subprocess.run(
                ["python3", str(inspector.__file__), str(spirv), "--built-object", str(built), "--save-temp-bitcode", str(saved)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("SHA-256 differ", completed.stderr)


if __name__ == "__main__":
    unittest.main()
