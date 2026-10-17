"""Spawn-safe admitted server entry; candidate gate runs before model warmup."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'driver'))
import server_entry  # Source-bound shutdown guards in every spawned PID.
from operator_gate import install

install()
if __name__ == '__main__':
    from vllm.entrypoints.cli.main import main
    main()
