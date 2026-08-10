#!/usr/bin/env python3
"""Offline fail-closed tests for run-validation runtime profiles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LANE = SCRIPT_DIR.parent
RUNNER = SCRIPT_DIR / "run-validation.sh"
CANONICAL_MANIFEST = LANE / "runtime-manifest.json"
VDR4_MANIFEST = LANE / "runtime-manifest-q8-vdr4-control.json"
VDR2_MANIFEST = LANE / "runtime-manifest-q8-vdr2-candidate.json"
VDR1_MANIFEST = LANE / "runtime-manifest-q8-vdr1-candidate.json"
CANONICAL_PROFILE = "canonical-baseline"
VDR4_PROFILE = "q8-vdr4-control"
VDR2_PROFILE = "q8-vdr2-candidate"
VDR1_PROFILE = "q8-vdr1-candidate"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RuntimeProfileTests(unittest.TestCase):
    def run_runner(
        self,
        *,
        runner: Path = RUNNER,
        profile: str | None = None,
        runtime_manifest: Path | None = None,
        llama_server: str | None = None,
        run_scope: str = "smoke",
        full512_band: str = "realistic",
        evidence_class: str = "legacy-validation",
        require_all_gpus_idle: str = "1",
        promotion_profile: str = "goal1-baseline-ub128",
        ubatch_size: str = "128",
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        run_dir = root / "must-not-be-created"
        environment = {
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": "C.UTF-8",
            "PATH": os.environ["PATH"],
            "RUN_SCOPE": run_scope,
            "FULL512_BAND": full512_band,
            "EVIDENCE_CLASS": evidence_class,
            "REQUIRE_ALL_GPUS_IDLE": require_all_gpus_idle,
            "PROMOTION_PROFILE": promotion_profile,
            "UBATCH_SIZE": ubatch_size,
            "MODEL": str(root / "deliberately-missing-model.gguf"),
            "RUN_DIR": str(run_dir),
        }
        if profile is not None:
            environment["RUNTIME_PROFILE"] = profile
        if runtime_manifest is not None:
            environment["RUNTIME_MANIFEST"] = str(runtime_manifest)
        if llama_server is not None:
            environment["LLAMA_SERVER"] = llama_server
        completed = subprocess.run(
            ["/usr/bin/bash", str(runner)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
        )
        return completed, run_dir

    def assert_reaches_missing_model_gate(
        self, completed: subprocess.CompletedProcess[str], run_dir: Path
    ) -> None:
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("model not found:", completed.stderr)
        self.assertNotIn("RUNTIME_PROFILE", completed.stderr)
        self.assertNotIn("runtime manifest", completed.stderr)
        self.assertFalse(run_dir.exists())

    def run_diagnostic_profile(
        self,
        profile: str,
        *,
        runner: Path = RUNNER,
        runtime_manifest: Path | None = None,
        llama_server: str | None = None,
        run_scope: str = "promotion512",
        full512_band: str = "short",
        evidence_class: str = "parallel-functional-screen",
        require_all_gpus_idle: str = "0",
        promotion_profile: str = "goal1-baseline-ub128",
        ubatch_size: str = "128",
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        return self.run_runner(
            runner=runner,
            profile=profile,
            runtime_manifest=runtime_manifest,
            llama_server=llama_server,
            run_scope=run_scope,
            full512_band=full512_band,
            evidence_class=evidence_class,
            require_all_gpus_idle=require_all_gpus_idle,
            promotion_profile=promotion_profile,
            ubatch_size=ubatch_size,
        )

    def test_implicit_canonical_default_is_unchanged(self) -> None:
        completed, run_dir = self.run_runner()
        self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_explicit_canonical_default_is_unchanged(self) -> None:
        completed, run_dir = self.run_runner(profile=CANONICAL_PROFILE)
        self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_registered_diagnostic_profiles_reach_model_gate(self) -> None:
        for profile in (VDR4_PROFILE, VDR2_PROFILE, VDR1_PROFILE):
            with self.subTest(profile=profile):
                completed, run_dir = self.run_diagnostic_profile(profile)
                self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_unknown_profile_fails_before_model_or_run_directory(self) -> None:
        for profile in ("", "q8-vdr3-unknown"):
            with self.subTest(profile=profile):
                completed, run_dir = self.run_runner(profile=profile)
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(f"invalid RUNTIME_PROFILE={profile}", completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_crossed_profile_manifest_pairs_fail_closed(self) -> None:
        for profile, manifest in (
            (VDR4_PROFILE, VDR2_MANIFEST),
            (VDR2_PROFILE, VDR4_MANIFEST),
            (VDR1_PROFILE, VDR2_MANIFEST),
            (VDR2_PROFILE, VDR1_MANIFEST),
            (CANONICAL_PROFILE, VDR4_MANIFEST),
        ):
            with self.subTest(profile=profile, manifest=manifest.name):
                if profile == CANONICAL_PROFILE:
                    completed, run_dir = self.run_runner(
                        profile=profile, runtime_manifest=manifest
                    )
                else:
                    completed, run_dir = self.run_diagnostic_profile(
                        profile, runtime_manifest=manifest
                    )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn("requires RUNTIME_MANIFEST=", completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_llama_server_override_mismatch_fails_closed(self) -> None:
        for profile in (VDR2_PROFILE, VDR1_PROFILE):
            with self.subTest(profile=profile):
                completed, run_dir = self.run_diagnostic_profile(
                    profile, llama_server="/definitely/wrong/llama-server"
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn("requires LLAMA_SERVER=", completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_noncanonical_scope_is_exactly_restricted(self) -> None:
        cases = (
            (
                {"run_scope": "smoke", "full512_band": "realistic"},
                "restricted to RUN_SCOPE=promotion512",
            ),
            (
                {"full512_band": "middle"},
                "restricted to FULL512_BAND=short",
            ),
            (
                {"evidence_class": "legacy-validation"},
                "requires EVIDENCE_CLASS=parallel-functional-screen or an explicitly authorized official-isolated profile",
            ),
            (
                {"require_all_gpus_idle": "1"},
                "with EVIDENCE_CLASS=parallel-functional-screen requires REQUIRE_ALL_GPUS_IDLE=0",
            ),
        )
        for profile in (VDR2_PROFILE, VDR1_PROFILE):
            for kwargs, expected in cases:
                with self.subTest(profile=profile, kwargs=kwargs):
                    completed, run_dir = self.run_diagnostic_profile(
                        profile, **kwargs
                    )
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn(expected, completed.stderr)
                    self.assertNotIn("model not found:", completed.stderr)
                    self.assertFalse(run_dir.exists())

    def test_vdr2_official_isolated_allowlist_reaches_model_gate(self) -> None:
        allowed = (
            ("short", "prefill-ub1024", "1024"),
            ("middle", "goal1-baseline-ub128", "128"),
            ("near32k", "prefill-ub1024", "1024"),
        )
        for band, promotion_profile, ubatch_size in allowed:
            with self.subTest(
                band=band,
                promotion_profile=promotion_profile,
                ubatch_size=ubatch_size,
            ):
                completed, run_dir = self.run_diagnostic_profile(
                    VDR2_PROFILE,
                    full512_band=band,
                    evidence_class="official-isolated",
                    require_all_gpus_idle="1",
                    promotion_profile=promotion_profile,
                    ubatch_size=ubatch_size,
                )
                self.assert_reaches_missing_model_gate(completed, run_dir)

    def test_vdr2_official_isolated_rejects_crossed_and_realistic_tuples(self) -> None:
        allowed = {
            ("short", "prefill-ub1024", "1024"),
            ("middle", "goal1-baseline-ub128", "128"),
            ("near32k", "prefill-ub1024", "1024"),
        }
        for band in ("short", "middle", "near32k", "realistic"):
            for promotion_profile in (
                "goal1-baseline-ub128",
                "prefill-ub1024",
            ):
                for ubatch_size in ("128", "1024"):
                    candidate = (band, promotion_profile, ubatch_size)
                    if candidate in allowed:
                        continue
                    with self.subTest(
                        band=band,
                        promotion_profile=promotion_profile,
                        ubatch_size=ubatch_size,
                    ):
                        completed, run_dir = self.run_diagnostic_profile(
                            VDR2_PROFILE,
                            full512_band=band,
                            evidence_class="official-isolated",
                            require_all_gpus_idle="1",
                            promotion_profile=promotion_profile,
                            ubatch_size=ubatch_size,
                        )
                        self.assertEqual(completed.returncode, 2, completed.stderr)
                        self.assertIn(
                            "requires short:prefill-ub1024:1024, "
                            "middle:goal1-baseline-ub128:128, or "
                            "near32k:prefill-ub1024:1024",
                            completed.stderr,
                        )
                        self.assertNotIn("model not found:", completed.stderr)
                        self.assertFalse(run_dir.exists())

    def test_vdr2_official_isolated_requires_all_gpus_idle(self) -> None:
        completed, run_dir = self.run_diagnostic_profile(
            VDR2_PROFILE,
            evidence_class="official-isolated",
            require_all_gpus_idle="0",
            promotion_profile="prefill-ub1024",
            ubatch_size="1024",
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn(
            "with EVIDENCE_CLASS=official-isolated requires REQUIRE_ALL_GPUS_IDLE=1",
            completed.stderr,
        )
        self.assertNotIn("model not found:", completed.stderr)
        self.assertFalse(run_dir.exists())

    def test_nonpromotable_profiles_remain_parallel_only(self) -> None:
        for profile in (VDR4_PROFILE, VDR1_PROFILE):
            with self.subTest(profile=profile):
                completed, run_dir = self.run_diagnostic_profile(
                    profile,
                    evidence_class="official-isolated",
                    require_all_gpus_idle="1",
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertIn(
                    "does not permit EVIDENCE_CLASS=official-isolated",
                    completed.stderr,
                )
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_vdr2_official_isolated_keeps_runtime_bindings(self) -> None:
        completed, run_dir = self.run_diagnostic_profile(
            VDR2_PROFILE,
            runtime_manifest=VDR4_MANIFEST,
            evidence_class="official-isolated",
            require_all_gpus_idle="1",
            promotion_profile="prefill-ub1024",
            ubatch_size="1024",
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("requires RUNTIME_MANIFEST=", completed.stderr)
        self.assertNotIn("model not found:", completed.stderr)
        self.assertFalse(run_dir.exists())

        completed, run_dir = self.run_diagnostic_profile(
            VDR2_PROFILE,
            llama_server="/definitely/wrong/llama-server",
            evidence_class="official-isolated",
            require_all_gpus_idle="1",
            promotion_profile="prefill-ub1024",
            ubatch_size="1024",
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("requires LLAMA_SERVER=", completed.stderr)
        self.assertNotIn("model not found:", completed.stderr)
        self.assertFalse(run_dir.exists())

    def copied_runner_with_manifest_value(
        self, *, profile_value: object, vdr_value: object
    ) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        temporary: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fixture_lane = root / "experiments/qwen36-27b-q8-gguf-b70"
        fixture_scripts = fixture_lane / "scripts"
        fixture_scripts.mkdir(parents=True)
        shutil.copy2(LANE / "model-manifest.json", fixture_lane / "model-manifest.json")
        shutil.copy2(CANONICAL_MANIFEST, fixture_lane / CANONICAL_MANIFEST.name)
        shutil.copy2(VDR4_MANIFEST, fixture_lane / VDR4_MANIFEST.name)
        value = json.loads(VDR2_MANIFEST.read_text())
        value["runtime_profile"] = profile_value
        value.setdefault("compile_time_controls", {})[
            "GGML_SYCL_REORDER_Q8_0_VDR_MMVQ"
        ] = vdr_value
        fixture_manifest = fixture_lane / VDR2_MANIFEST.name
        fixture_manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

        source = RUNNER.read_text()
        old_sha = sha256_file(VDR2_MANIFEST)
        new_sha = sha256_file(fixture_manifest)
        self.assertEqual(source.count(old_sha), 1)
        fixture_runner = fixture_scripts / RUNNER.name
        fixture_runner.write_text(source.replace(old_sha, new_sha))
        fixture_runner.chmod(0o755)
        return fixture_runner, temporary

    def test_manifest_profile_and_vdr_declarations_are_strict(self) -> None:
        malformed = (
            ("wrong-profile", 2, "runtime manifest runtime_profile mismatch"),
            (VDR2_PROFILE, 3, "expected integer 2"),
            (VDR2_PROFILE, "2", "expected integer 2"),
            (VDR2_PROFILE, True, "expected integer 2"),
        )
        for profile_value, vdr_value, expected in malformed:
            with self.subTest(profile_value=profile_value, vdr_value=vdr_value):
                fixture_runner, _ = self.copied_runner_with_manifest_value(
                    profile_value=profile_value, vdr_value=vdr_value
                )
                completed, run_dir = self.run_diagnostic_profile(
                    VDR2_PROFILE, runner=fixture_runner
                )
                self.assertEqual(completed.returncode, 1, completed.stderr)
                self.assertIn(expected, completed.stderr)
                self.assertNotIn("model not found:", completed.stderr)
                self.assertFalse(run_dir.exists())

    def test_profiles_are_bound_into_all_retained_identity_layers(self) -> None:
        source = RUNNER.read_text()
        self.assertIn(
            'LABEL="${LABEL}-${RUNTIME_PROFILE}-vdr${RUNTIME_PROFILE_EXPECTED_Q8_VDR}"',
            source,
        )
        self.assertIn('echo "runtime_profile=$RUNTIME_PROFILE"', source)
        self.assertIn(
            'echo "declared_q8_reorder_vdr_mmvq=$RUNTIME_DECLARED_Q8_VDR"',
            source,
        )
        self.assertIn('runtime_profile:$runtime_profile', source)
        self.assertIn('"evidence_class": evidence_class', source)
        self.assertIn(
            '"runtime_profile_official_isolated_promotable": '
            "official_isolated_promotable",
            source,
        )
        self.assertIn(
            'declared_q8_reorder_vdr_mmvq:$declared_q8_reorder_vdr_mmvq',
            source,
        )
        self.assertIn('"server_identity_fields": runtime_identity_fields', source)
        self.assertIn('elif $runtime_profile == "q8-vdr2-candidate" then', source)
        self.assertIn('elif $runtime_profile == "q8-vdr1-candidate" then', source)
        self.assertIn(
            "only q8-vdr2-candidate official-isolated with all GPUs idle may be "
            "performance_promotable",
            source,
        )


if __name__ == "__main__":
    unittest.main()
