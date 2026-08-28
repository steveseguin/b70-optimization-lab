from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
TOOL = HERE / "prepare-dependencies.py"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_hash(data: bytes) -> str:
    value = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + value.decode("ascii")


def build_wheel(path: Path) -> None:
    members = {
        "demo_pkg/__init__.py": b"__version__ = '1.0'\n",
        "demo_pkg-1.0.dist-info/METADATA": (
            b"Metadata-Version: 2.1\nName: demo-pkg\nVersion: 1.0\n"
        ),
        "demo_pkg-1.0.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: packet-test\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    rows = [
        [name, record_hash(data), str(len(data))] for name, data in members.items()
    ]
    rows.append(["demo_pkg-1.0.dist-info/RECORD", "", ""])
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    members["demo_pkg-1.0.dist-info/RECORD"] = output.getvalue().encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)


class PrepareDependenciesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.wheelhouse = self.root / "wheelhouse"
        self.wheelhouse.mkdir()
        self.wheel = self.wheelhouse / "demo_pkg-1.0-py3-none-any.whl"
        build_wheel(self.wheel)
        self.lock = self.root / "requirements.lock"
        self.lock.write_text(
            f"demo-pkg==1.0 --hash=sha256:{digest(self.wheel.read_bytes())}\n",
            encoding="utf-8",
        )
        lock_sha = digest(self.lock.read_bytes())
        self.dependency_contract = self.root / "dependency-contract.json"
        self.dependency_contract.write_text(
            json.dumps(
                {
                    "format": "test-dependency-contract-v1",
                    "status": "dependency-installable",
                    "python": {
                        "implementation": sys.implementation.name,
                        "major_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
                    },
                    "requirements_runtime_lock_sha256": lock_sha,
                    "allowed_unlocked_distributions": ["pip", "setuptools"],
                }
            ),
            encoding="utf-8",
        )
        self.wheelhouse_contract = self.root / "wheelhouse-contract.json"
        self.write_wheelhouse_contract(lock_sha)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_wheelhouse_contract(self, lock_sha: str, **overrides: object) -> None:
        item = {
            "name": self.wheel.name,
            "distribution": "demo-pkg",
            "version": "1.0",
            "size_bytes": self.wheel.stat().st_size,
            "sha256": digest(self.wheel.read_bytes()),
        }
        item.update(overrides)
        self.wheelhouse_contract.write_text(
            json.dumps(
                {
                    "format": "test-wheelhouse-contract-v1",
                    "status": "complete-binary-wheelhouse",
                    "requirements_runtime_lock_sha256": lock_sha,
                    "files": [item],
                }
            ),
            encoding="utf-8",
        )

    def run_tool(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--wheelhouse",
                str(self.wheelhouse),
                "--output-venv",
                str(self.root / "venv"),
                "--receipt",
                str(self.root / "receipt.json"),
                "--dependency-contract",
                str(self.dependency_contract),
                "--wheelhouse-contract",
                str(self.wheelhouse_contract),
                "--lock",
                str(self.lock),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_valid_exact_wheel_installs_offline(self) -> None:
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.root / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "offline-install-complete")
        self.assertEqual(receipt["wheel_count"], 1)
        probe = subprocess.run(
            [str(self.root / "venv/bin/python"), "-c", "import demo_pkg"],
            check=False,
        )
        self.assertEqual(probe.returncode, 0)

    def test_observed_only_contract_creates_nothing(self) -> None:
        contract = json.loads(self.dependency_contract.read_text())
        contract["status"] = "dependency-observed"
        self.dependency_contract.write_text(json.dumps(contract), encoding="utf-8")
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("observed-only", result.stderr)
        self.assertFalse((self.root / "venv").exists())

    def test_hash_mismatch_creates_nothing(self) -> None:
        lock_sha = digest(self.lock.read_bytes())
        self.write_wheelhouse_contract(lock_sha, sha256="0" * 64)
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("identity mismatch", result.stderr)
        self.assertFalse((self.root / "venv").exists())

    def test_extra_wheel_is_rejected(self) -> None:
        (self.wheelhouse / "extra-1-py3-none-any.whl").write_bytes(b"extra")
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("inventory mismatch", result.stderr)

    def test_mutable_lock_source_is_rejected(self) -> None:
        self.lock.write_text("-e git+https://example.invalid/repo#egg=demo\n")
        lock_sha = digest(self.lock.read_bytes())
        contract = json.loads(self.dependency_contract.read_text())
        contract["requirements_runtime_lock_sha256"] = lock_sha
        self.dependency_contract.write_text(json.dumps(contract), encoding="utf-8")
        self.write_wheelhouse_contract(lock_sha)
        result = self.run_tool()
        self.assertEqual(result.returncode, 2)
        self.assertIn("mutable or direct source", result.stderr)


if __name__ == "__main__":
    unittest.main()
