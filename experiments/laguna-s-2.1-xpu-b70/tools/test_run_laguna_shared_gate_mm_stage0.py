"""CPU-only structural tests for the stage-zero runtime adapter.

Do not add torch/vLLM imports or call ``main`` here: that would blur the
pre-tensor boundary the adapter is designed to enforce.
"""

from __future__ import annotations

import ast
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_laguna_shared_gate_mm_stage0 as adapter
import gate_laguna_shared_gate_mm_stage0 as stage0


def _packet() -> dict[str, object]:
    return {
        "tools": {},
        "source": {},
        "authorization_tracking": {},
        "runtime": {},
        "binaries": {},
        "model": {},
        "storage": {},
        "device": {},
        "boot_id": "test-boot",
        "protocol": {},
        "argv": [],
        "runner_argv": [],
        "environment": {},
        "packet_path": "/mnt/fast-ai/packet.json",
    }


def test_base_result_is_reachable_and_pre_tensor() -> None:
    result = adapter._base_result(
        _packet(), {"manifest_sha256": "f" * 64}, started="2026-07-23T00:00:00Z"
    )
    assert result["status"] == "stage0_pre_tensor_failure"
    assert result["tensor_work_started"] is False
    assert result["dispatch_proof"] is None
    assert result["epochs"] == []
    assert result["error"] is None


def test_tensor_started_checkpoint_is_terminal_evidence() -> None:
    result = adapter._base_result(
        _packet(), {"manifest_sha256": "f" * 64}, started="2026-07-23T00:00:00Z"
    )
    result["tensor_work_started"] = True
    payload = adapter._tensor_started_payload(result)
    assert payload["tensor_work_started"] is True
    assert payload["authorization_packet"] == result["authorization_packet"]


def test_adapter_has_no_top_level_runtime_import() -> None:
    path = Path(adapter.__file__)
    tree = ast.parse(path.read_text())
    forbidden = {"torch", "vllm", "time", "profile", "cProfile"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & forbidden
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] not in forbidden


def test_containment_is_resolved_not_string_prefix() -> None:
    root = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/run")
    assert adapter._is_within(root / "a.json", root)
    assert not adapter._is_within(Path("/mnt/fast-ai/other/a.json"), root)


def test_runtime_directories_are_created_only_under_owned_root(tmp_path) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    adapter._create_runtime_directories(root)
    for relative in adapter.RUNTIME_RELATIVE_DIRECTORIES:
        path = root / relative
        assert path.is_dir()
        assert path.resolve().is_relative_to(root.resolve())


def test_shell_runner_is_syntax_clean_and_no_precreate_launcher() -> None:
    path = Path(adapter.__file__).with_suffix(".sh")
    text = path.read_text()
    completed = subprocess.run(
        ["/usr/bin/bash", "-n", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert path.stat().st_mode & stat.S_IXUSR
    assert "[[ $OUTPUT_ROOT == /* && ! -e $OUTPUT_ROOT" in text
    assert 'exec "$ENV" -i "${ENVIRONMENT[@]}" "${ADAPTER_ARGV[@]}"' in text
    for forbidden in ("xpu-smi", "curl ", "wget ", "tee ", "time ", "perf "):
        assert forbidden not in text


class _FakeXpu:
    def __init__(self) -> None:
        self.count = 1
        self.current = 0
        self.name = stage0.EXPECTED_DEVICE_NAME

    def device_count(self) -> int:
        return self.count

    def current_device(self) -> int:
        return self.current

    def get_device_name(self, _index: int) -> str:
        return self.name


class _FakeTorch:
    def __init__(self) -> None:
        self.xpu = _FakeXpu()
        self.tensor_device = "xpu:0"
        self.__version__ = "2.12.0+xpu"
        self.__file__ = stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY["files"][
            "torch_init"
        ]["path"]
        self.version = SimpleNamespace(
            __file__=stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY["files"][
                "torch_version"
            ]["path"]
        )

    def empty(self, _shape, *, device: str):
        assert device == "xpu"
        return SimpleNamespace(device=self.tensor_device)


def _binding_inputs() -> tuple[dict, dict]:
    return (
        {
            "device": dict(stage0.EXPECTED_CARD0),
            "runtime": {"observed_identity": stage0.EXPECTED_RUNTIME_OBSERVED_IDENTITY},
        },
        {
            "sysfs_card0": {
                "drm_device": stage0.EXPECTED_CARD0["drm_device"],
                "pci_bdf_address": stage0.EXPECTED_CARD0["pci_bdf_address"],
                "vendor": "0x8086",
                "device": "0xe223",
            }
        },
    )


def test_runtime_card0_binding_with_fake_torch(monkeypatch) -> None:
    monkeypatch.setenv("ONEAPI_DEVICE_SELECTOR", "level_zero:0")
    monkeypatch.setenv("ZE_AFFINITY_MASK", "0")
    packet, observed = _binding_inputs()
    binding = adapter._runtime_card0_binding(_FakeTorch(), packet, observed)
    assert binding["packet_device"] == stage0.EXPECTED_CARD0
    assert binding["tensor_device"] == "xpu:0"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("count", 2),
        ("current", 1),
        ("name", "Intel(R) Arc(TM) Pro B60 Graphics"),
        ("tensor_device", "xpu:1"),
    ],
)
def test_runtime_card0_binding_rejects_fake_runtime_drift(
    monkeypatch, field: str, value
) -> None:
    monkeypatch.setenv("ONEAPI_DEVICE_SELECTOR", "level_zero:0")
    monkeypatch.setenv("ZE_AFFINITY_MASK", "0")
    packet, observed = _binding_inputs()
    torch = _FakeTorch()
    target = torch if field == "tensor_device" else torch.xpu
    setattr(target, field, value)
    with pytest.raises(RuntimeError):
        adapter._runtime_card0_binding(torch, packet, observed)


def test_runtime_card0_binding_rejects_selector_drift(monkeypatch) -> None:
    monkeypatch.setenv("ONEAPI_DEVICE_SELECTOR", "level_zero:1")
    monkeypatch.setenv("ZE_AFFINITY_MASK", "0")
    packet, observed = _binding_inputs()
    with pytest.raises(RuntimeError, match="selectors"):
        adapter._runtime_card0_binding(_FakeTorch(), packet, observed)


def test_runtime_exception_classifier_never_claims_exactness() -> None:
    result = adapter._base_result(
        _packet(), {"manifest_sha256": "f" * 64}, started="2026-07-23T00:00:00Z"
    )
    result["tensor_work_started"] = True
    result["execution_phase"] = "tensor_work_started"
    result["last_durable_checkpoint"] = "tensor_work_started"
    adapter._mark_runtime_infrastructure_failure(result, ValueError("runtime broke"))
    assert result["status"] == "stage0_runtime_infrastructure_failed_stop"
    assert result["error"] == {
        "class": "runtime_infrastructure_failure",
        "phase": "tensor_work_started",
        "exception_type": "ValueError",
        "message": "runtime broke",
        "proven": False,
        "proof": None,
    }
