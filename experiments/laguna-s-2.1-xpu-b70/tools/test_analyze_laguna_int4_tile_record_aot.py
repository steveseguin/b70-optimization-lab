import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("analyze_laguna_int4_tile_record_aot.py")
SPEC = importlib.util.spec_from_file_location("tile_record_aot", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _assembly(
    enabled: bool,
    *,
    instructions: int = 370,
    alu: int = 320,
    sync: int = 9,
    grf: int = 128,
    extra: str = "",
) -> str:
    flag = "1" if enabled else "0"
    return f"""//.kernel _ZTS25LagunaInt4TileRecordProbeILb{flag}EE
//.thread_config numGRF={grf}, numAcc=4, numSWSB=16
//.instCount {instructions}
        mul (16|M0) r1:bf r2:bf r3:f
        mul (16|M0) r1:bf r2:bf r3:f
{"".join("        mul (16|M0) r1:bf r2:bf r3:f\n" for _ in range(31))}\
        dpas.8x8 (16|M0) r1:f r1:f r2:bf r3:bf
        dpas.8x8 (16|M0) r1:f r1:f r2:bf r3:bf
        load_block2d.ugm.d8.a64.ca.ca (1|M0) null:0 [r1:1]
        send.gtwy (1|M0) null r1 null:0 0x0 0x02000004
{extra}//.numALUInst: {alu}
//.syncInstCount: {sync}
"""


def _pair(tmp_path: Path, *, candidate_kwargs: dict | None = None) -> Path:
    (tmp_path / "control.asm").write_text(_assembly(False))
    kwargs = candidate_kwargs or {}
    (tmp_path / "candidate.asm").write_text(_assembly(True, **kwargs))
    return tmp_path


def test_exact_affine_candidate_passes(tmp_path: Path) -> None:
    report = MODULE.analyze(
        _pair(tmp_path, candidate_kwargs={"instructions": 378, "alu": 328})
    )
    assert report["status"] == "pass"
    assert report["delta"]["instructions"] == 8


def test_instruction_regression_fails(tmp_path: Path) -> None:
    report = MODULE.analyze(
        _pair(tmp_path, candidate_kwargs={"instructions": 379, "alu": 329})
    )
    assert report["status"] == "fail"
    assert not report["checks"]["candidate_instruction_ceiling"]


def test_executable_scratch_marker_fails_without_header_false_positive(
    tmp_path: Path,
) -> None:
    report = MODULE.analyze(
        _pair(
            tmp_path,
            candidate_kwargs={
                "extra": "send.ugm (1|M0) null r1 // scratch spill write\n"
            },
        )
    )
    assert report["status"] == "fail"
    assert not report["checks"]["no_executable_spill_or_scratch"]


def test_duplicate_candidate_is_rejected(tmp_path: Path) -> None:
    _pair(tmp_path)
    (tmp_path / "candidate-copy.asm").write_text(_assembly(True))
    report = MODULE.analyze(tmp_path)
    assert report["status"] == "fail"
    assert "expected exactly one candidate assembly, found 2" in report["errors"]


def test_nonmatching_assemblies_are_ignored(tmp_path: Path) -> None:
    _pair(tmp_path)
    (tmp_path / "other.asm").write_text("//.kernel unrelated\n")
    assert MODULE.analyze(tmp_path)["status"] == "pass"
