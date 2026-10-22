"""Entry point to the exact two-range suite checker; CPU read-only."""
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[4]
runpy.run_path(str(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/suite_check.py'),run_name='__main__')
