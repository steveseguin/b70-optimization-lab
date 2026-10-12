"""Run the exact long-oracle checker; standard library only."""
import runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
runpy.run_path(str(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/suite_check.py'),run_name='__main__')
