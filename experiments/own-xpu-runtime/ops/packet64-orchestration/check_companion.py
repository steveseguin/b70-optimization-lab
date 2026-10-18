"""Passive CPU companion preflight, before acquiring any lane reservation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
LANES = ROOT / 'experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes'
sys.path.insert(0, str(LANES))
from conditions import cpu_gate
from cpu_seal import verify
import fault_review

if __name__ == '__main__':
    cpu_gate()
    verify()
    fault_review.validate(Path(sys.argv[1]))
    print('Companion CPU seal and existing boot-bound review verified; no device or reservation opened')
