#!/usr/bin/env python3
"""Offline fail-closed tests for the canonical Q8 launcher control."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LAUNCHER = SCRIPT_DIR / "serve-target-only.sh"
SERVER_ATTESTER = SCRIPT_DIR / "attest-c2-server.py"
BASELINE_MANIFEST = SCRIPT_DIR.parent / "runtime-manifest.json"
CANDIDATE_MANIFEST = SCRIPT_DIR.parent / "runtime-manifest-canonical-q8-c2.json"
CONTROL = "GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_server_attester():
    spec = importlib.util.spec_from_file_location("c2_server_attester", SERVER_ATTESTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LauncherControlTests(unittest.TestCase):
    def environment(self, manifest: Path, value: str | None) -> dict[str, str]:
        environment = os.environ.copy()
        for name in list(environment):
            if name.startswith(("GGML_", "SYCL_", "ZE_", "ZES_", "UR_")):
                environment.pop(name)
            elif name in {"ONEAPI_DEVICE_SELECTOR", "LD_PRELOAD"}:
                environment.pop(name)
            elif name.startswith("LLAMA_"):
                environment.pop(name)
            elif name.startswith("QWEN36_"):
                environment.pop(name)
        environment.update(
            {
                "MODEL": "/definitely/missing/qwen36-q8-control-test.gguf",
                "RUNTIME_MANIFEST": str(manifest),
            }
        )
        if value is None:
            environment.pop("LANE_Q8_0_C2_CANONICAL_MMVQ", None)
        else:
            environment["LANE_Q8_0_C2_CANONICAL_MMVQ"] = value
        return environment

    def run_launcher(
        self,
        manifest: Path = BASELINE_MANIFEST,
        value: str | None = None,
        *,
        arguments: tuple[str, ...] = (),
        extra_environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = self.environment(manifest, value)
        if extra_environment is not None:
            environment.update(extra_environment)
        return subprocess.run(
            ["bash", str(LAUNCHER), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    def write_manifest(self, directory: Path, control: object) -> Path:
        value = json.loads(BASELINE_MANIFEST.read_text())
        value["experimental_controls"] = {CONTROL: control}
        path = directory / "runtime-manifest.json"
        path.write_text(json.dumps(value))
        return path

    def test_incumbent_default_remains_selector_absent(self) -> None:
        completed = self.run_launcher()
        self.assertEqual(completed.returncode, 2)
        self.assertIn("model not found", completed.stderr)
        self.assertNotIn("supporting runtime manifest", completed.stderr)

    def test_selector_one_rejects_incumbent_manifest_before_model_work(self) -> None:
        completed = self.run_launcher(value="1")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("requires a supporting runtime manifest", completed.stderr)
        self.assertNotIn("model not found", completed.stderr)

    def test_selector_value_is_strict_boolean(self) -> None:
        for value in ("", "2", "-1", "1x", "true"):
            with self.subTest(value=value):
                completed = self.run_launcher(value=value)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("must be 0 or 1", completed.stderr)

    def test_sleep_idle_control_is_strict_and_default_disabled(self) -> None:
        for value in ("", "0", "-2", "1x", "3601"):
            with self.subTest(value=value):
                completed = self.run_launcher(
                    extra_environment={"SLEEP_IDLE_SECONDS": value}
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn("SLEEP_IDLE_SECONDS", completed.stderr)
                self.assertNotIn("model not found", completed.stderr)
        completed = self.run_launcher(extra_environment={"SLEEP_IDLE_SECONDS": "60"})
        self.assertEqual(completed.returncode, 2)
        self.assertIn("model not found", completed.stderr)

    def test_attester_opt_in_sleep_identity_preserves_default_contract(self) -> None:
        attester = load_server_attester()
        default = attester.build_attestation("", "", 1, "a" * 64, 1024)
        self.assertNotIn("sleep_idle_seconds", default["expected_identity"])
        opted_in = attester.build_attestation(
            "",
            "sleep_idle_seconds=60\nargv=llama-server --sleep-idle-seconds 60\n",
            1,
            "a" * 64,
            1024,
            60,
        )
        self.assertEqual(opted_in["expected_identity"]["sleep_idle_seconds"], "60")
        self.assertTrue(opted_in["identity_fields"]["sleep_idle_seconds"])
        self.assertTrue(opted_in["argv_fields"]["--sleep-idle-seconds 60"])
        for argv in (
            "llama-server --sleep-idle-seconds 600",
            "llama-server --sleep-idle-seconds 60 --sleep-idle-seconds 60",
        ):
            with self.subTest(argv=argv):
                malformed = attester.build_attestation(
                    "",
                    f"sleep_idle_seconds=60\nargv={argv}\n",
                    1,
                    "a" * 64,
                    1024,
                    60,
                )
                self.assertFalse(malformed["argv_fields"]["--sleep-idle-seconds 60"])

    def test_exact_manifest_contract_allows_selector_zero_and_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_manifest(
                Path(directory),
                {
                    "supported": True,
                    "default": "0",
                    "values": ["0", "1"],
                    "note": "additional provenance fields are permitted",
                },
            )
            for value in ("0", "1"):
                with self.subTest(value=value):
                    completed = self.run_launcher(manifest, value)
                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("model not found", completed.stderr)
                    self.assertNotIn("supporting runtime manifest", completed.stderr)

    def test_malformed_declared_control_fails_even_when_selector_is_zero(self) -> None:
        malformed_controls = (
            None,
            {"supported": False, "default": "0", "values": ["0", "1"]},
            {"supported": True, "default": 0, "values": ["0", "1"]},
            {"supported": True, "default": "0", "values": [0, 1]},
            {"supported": True, "default": "0", "values": ["1", "0"]},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, control in enumerate(malformed_controls):
                with self.subTest(index=index, control=control):
                    manifest = self.write_manifest(root, control)
                    completed = self.run_launcher(manifest, "0")
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("experimental_controls", completed.stderr)
                    self.assertNotIn("model not found", completed.stderr)

    def test_selector_one_requires_optimization_lane(self) -> None:
        completed = self.run_launcher(
            CANDIDATE_MANIFEST,
            "1",
            extra_environment={"LANE_OPT_ENABLED": "0"},
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("requires LANE_OPT_ENABLED=1", completed.stderr)
        self.assertNotIn("model not found", completed.stderr)

    def test_inherited_raw_candidate_controls_are_rejected(self) -> None:
        for name in (CONTROL, "GGML_SYCL_PRIORITIZE_DMMV"):
            with self.subTest(name=name):
                completed = self.run_launcher(
                    CANDIDATE_MANIFEST,
                    "1",
                    extra_environment={name: "1"},
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn(
                    "unexpected inherited runtime environment", completed.stderr
                )
                self.assertIn(name, completed.stderr)
                self.assertNotIn("model not found", completed.stderr)

    def test_malformed_runtime_loader_policy_fails_before_model_work(self) -> None:
        malformed_policies = (
            None,
            [],
            {},
            {"mode": "runpath-default", "variable": "LD_LIBRARY_PATH"},
            {"mode": "origin-first", "variable": "PATH"},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, policy in enumerate(malformed_policies):
                with self.subTest(index=index, policy=policy):
                    value = json.loads(BASELINE_MANIFEST.read_text())
                    value["runtime_loader_policy"] = policy
                    manifest = root / f"runtime-manifest-{index}.json"
                    manifest.write_text(json.dumps(value))
                    completed = self.run_launcher(manifest)
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("runtime_loader_policy", completed.stderr)
                    self.assertNotIn("model not found", completed.stderr)

    def test_candidate_bundle_origin_first_resolution_is_attested(self) -> None:
        if not CANDIDATE_MANIFEST.is_file():
            self.skipTest(f"candidate manifest is absent: {CANDIDATE_MANIFEST}")
        if not Path("/opt/intel/oneapi/setvars.sh").is_file():
            self.skipTest("oneAPI environment is unavailable")
        if shutil.which("ldd") is None:
            self.skipTest("ldd is unavailable")

        manifest = json.loads(CANDIDATE_MANIFEST.read_text())
        binary = Path(manifest["llama_server_path"])
        if not binary.is_file():
            self.skipTest(f"candidate runtime bundle is absent: {binary.parent}")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ldd_output = root / "candidate.ldd"
            hashes_output = root / "candidate.sha256"
            report_output = root / "candidate-report.json"
            completed = self.run_launcher(
                CANDIDATE_MANIFEST,
                arguments=(
                    "--verify-runtime-bundle",
                    str(ldd_output),
                    str(hashes_output),
                    str(report_output),
                ),
                extra_environment={"LLAMA_SERVER": str(binary)},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            report = json.loads(report_output.read_text())
            policy = report["loader_policy"]
            self.assertEqual(policy["mode"], "origin-first")
            self.assertEqual(policy["variable"], "LD_LIBRARY_PATH")
            self.assertEqual(policy["binary_origin"], str(binary.parent))
            self.assertEqual(policy["ld_library_path_first"], str(binary.parent))
            self.assertTrue(policy["origin_precedence_attested"])

            expected = {
                entry["soname"]: entry for entry in manifest["origin_shared_objects"]
            }
            observed = {
                entry["soname"]: entry
                for entry in report["dependencies"]
                if entry["soname"] in expected
            }
            self.assertEqual(len(expected), 8)
            self.assertEqual(set(observed), set(expected))
            self.assertEqual(report["origin_shared_object_count"], 8)
            self.assertEqual(set(report["origin_shared_object_sonames"]), set(expected))
            origin_prefix = f"{binary.parent}{os.sep}"
            for soname, dependency in observed.items():
                with self.subTest(soname=soname):
                    self.assertTrue(dependency["loader_path"].startswith(origin_prefix))
                    self.assertTrue(
                        dependency["resolved_path"].startswith(origin_prefix)
                    )
                    self.assertEqual(dependency["sha256"], expected[soname]["sha256"])
                    self.assertEqual(
                        dependency["size_bytes"], expected[soname]["size_bytes"]
                    )

    def test_fake_exec_binds_runner_identity_and_stdout_pid_without_overwrite(
        self,
    ) -> None:
        compiler = shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler is unavailable")
        if not Path("/opt/intel/oneapi/setvars.sh").is_file():
            self.skipTest("oneAPI environment is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "runtime"
            fake_bin = root / "fake-bin"
            output_dir = root / "output"
            bundle.mkdir()
            fake_bin.mkdir()
            output_dir.mkdir()

            library_source = root / "fixture.c"
            server_source = root / "server.c"
            library_source.write_text("int fixture_value(void) { return 7; }\n")
            server_source.write_text(
                """#include <stdio.h>
#include <string.h>
#include <unistd.h>
extern int fixture_value(void);
int main(int argc, char **argv) {
    if (fixture_value() != 7) return 9;
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        puts("version: fake-process-binding");
        return 0;
    }
    printf("FAKE_LLAMA_SERVER pid=%ld\\n", (long) getpid());
    fflush(stdout);
    return 0;
}
"""
            )
            library = bundle / "libfixture.so.1"
            subprocess.run(
                [
                    compiler,
                    "-shared",
                    "-fPIC",
                    "-Wl,-soname,libfixture.so.1",
                    str(library_source),
                    "-o",
                    str(library),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            (bundle / "libfixture.so").symlink_to(library.name)
            server = bundle / "llama-server"
            subprocess.run(
                [
                    compiler,
                    str(server_source),
                    f"-L{bundle}",
                    "-Wl,--no-as-needed",
                    "-lfixture",
                    f"-Wl,-rpath,{bundle}",
                    "-o",
                    str(server),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            manifest = root / "runtime-manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "runtime_bundle_schema_version": 1,
                        "runtime_loader_policy": {
                            "mode": "origin-first",
                            "variable": "LD_LIBRARY_PATH",
                        },
                        "runtime_version_line": "version: fake-process-binding",
                        "llama_server_path": str(server),
                        "llama_server_sha256": sha256_file(server),
                        "origin_shared_objects": [
                            {
                                "soname": "libfixture.so.1",
                                "loader_path": "$ORIGIN/libfixture.so.1",
                                "resolved_path": "$ORIGIN/libfixture.so.1",
                                "size_bytes": library.stat().st_size,
                                "sha256": sha256_file(library),
                            }
                        ],
                        "experimental_controls": {
                            CONTROL: {
                                "supported": True,
                                "default": "0",
                                "values": ["0", "1"],
                            }
                        },
                    }
                )
            )

            expected_model_size = json.loads(
                (SCRIPT_DIR.parent / "model-manifest.json").read_text()
            )["size_bytes"]
            model = root / "sparse-model.gguf"
            with model.open("wb") as stream:
                stream.truncate(expected_model_size)

            for name in ("flock", "ss"):
                command = fake_bin / name
                command.write_text("#!/bin/sh\nexit 0\n")
                command.chmod(0o755)

            modes = (("server-output", "60"), ("wrapper-output", "-1"))
            for index, (outer_mode, sleep_idle) in enumerate(modes):
                with self.subTest(outer_mode=outer_mode, sleep_idle=sleep_idle):
                    run_dir = output_dir / outer_mode
                    run_dir.mkdir()
                    identity_log = run_dir / "server.identity.log"
                    server_output = run_dir / "server.stdout.log"
                    wrapper_output = run_dir / "launcher.stdout.log"
                    outer_path = (
                        server_output
                        if outer_mode == "server-output"
                        else wrapper_output
                    )
                    environment = self.environment(manifest, "0")
                    environment.update(
                        {
                            "GPU_INDEX": "3",
                            "PORT": str(29647 + index),
                            "MODEL": str(model),
                            "LLAMA_SERVER": str(server),
                            "LOG": str(identity_log),
                            "SERVER_OUTPUT_LOG": str(server_output),
                            "OUT_DIR": str(run_dir),
                            "SLEEP_IDLE_SECONDS": sleep_idle,
                            "PATH": (f"{fake_bin}{os.pathsep}{environment['PATH']}"),
                        }
                    )
                    with outer_path.open("wb") as outer_stdout:
                        process = subprocess.Popen(
                            ["bash", str(LAUNCHER)],
                            stdout=outer_stdout,
                            stderr=subprocess.STDOUT,
                            env=environment,
                        )
                        runner_pid = str(process.pid)
                        returncode = process.wait(timeout=30)

                    self.assertEqual(returncode, 0)
                    identity_lines = identity_log.read_text().splitlines()
                    output_lines = server_output.read_text().splitlines()
                    self.assertEqual(
                        identity_lines.count(f"server_pid={runner_pid}"), 1
                    )
                    self.assertEqual(
                        identity_lines.count(
                            f"server_output_log={server_output.resolve()}"
                        ),
                        1,
                    )
                    self.assertEqual(identity_lines.count("--- server ---"), 1)
                    self.assertEqual(
                        identity_lines.count(f"sleep_idle_seconds={sleep_idle}"), 1
                    )
                    argv_line = next(
                        line for line in identity_lines if line.startswith("argv=")
                    )
                    expected_sleep_argv_count = 1 if sleep_idle == "60" else 0
                    self.assertEqual(
                        argv_line.count("--sleep-idle-seconds 60"),
                        expected_sleep_argv_count,
                    )
                    self.assertNotEqual(identity_log.resolve(), server_output.resolve())
                    self.assertEqual(
                        output_lines,
                        [
                            f"QWEN36_SERVER_PROCESS_BINDING pid={runner_pid}",
                            f"FAKE_LLAMA_SERVER pid={runner_pid}",
                        ],
                    )
                    if outer_mode == "wrapper-output":
                        self.assertEqual(wrapper_output.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
