#!/usr/bin/env python3
"""Q8-KV validator mechanically overlaid on the passed F16 expansion gates."""

from pathlib import Path
import sys
from types import ModuleType


HERE = Path(__file__).resolve().parent
F16_VALIDATOR = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py"


def transformed_source() -> str:
    source = F16_VALIDATOR.read_text(encoding="utf-8")
    replacements = (
        ("run-20260825-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1.py", "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1.py", 1),
        ("qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-20260825-r1", "qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-20260825-r1", 1),
        ("neural.download.qwen36-llama-mtp124-exact-depth-quality-terminal.v1", "neural.download.qwen36-llama-mtp1234-q8kv-exact-depth-quality-terminal.v1", 1),
        ("ROUTES = (0, 1, 2, 4)", "ROUTES = (0, 1, 2, 3, 4)", 1),
        ('ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 4: "candidate-mtp4"}', 'ARMS = {0: "control-mtp0", 1: "candidate-mtp1", 2: "candidate-mtp2", 3: "candidate-mtp3", 4: "candidate-mtp4"}', 1),
        ("[1, 2, 4]", "[1, 2, 3, 4]", 1),
        ("(1, 2, 4)", "(1, 2, 3, 4)", 1),
        ('route = flag_value(argv, "--spec-type") == "none" if mtp == 0 else flag_value(argv, "--spec-type") == "draft-mtp" and flag_value(argv, "--spec-draft-n-max") == str(mtp) and flag_value(argv, "--spec-draft-n-min") == "0"', 'route = flag_value(argv, "--spec-type") == "none" if mtp == 0 else flag_value(argv, "--spec-type") == "draft-mtp" and flag_value(argv, "--spec-draft-n-max") == str(mtp) and flag_value(argv, "--spec-draft-n-min") == "0" and flag_value(argv, "--spec-draft-type-k") == "q8_0" and flag_value(argv, "--spec-draft-type-v") == "q8_0"', 1),
        ('== "f16"', '== "q8_0"', 1),
    )
    for old, new, expected in replacements:
        count = source.count(old)
        if count != expected: raise RuntimeError(f"validator transform drift {old!r}: {count}")
        source = source.replace(old, new)
    return source


source = transformed_source(); BASE = ModuleType("qwen36_q8kv_mtp1234_validator_transformed"); BASE.__file__ = str(F16_VALIDATOR); BASE.__package__ = None; sys.modules[BASE.__name__] = BASE; exec(compile(source, str(F16_VALIDATOR), "exec"), BASE.__dict__)
validate = BASE.validate


def main() -> int: return BASE.main()


if __name__ == "__main__": raise SystemExit(main())
