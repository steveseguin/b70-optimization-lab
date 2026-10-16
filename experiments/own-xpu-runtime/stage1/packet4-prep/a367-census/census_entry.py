"""Spawn-safe census entry. Runtime imports occur only in an admitted launch."""
from pathlib import Path
import sys

# Reuse the protected driver bootstrap byte-for-byte, without editing it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "driver"))
import server_entry  # Installs source-bound cleanup guards in every spawned PID.
from trace_marks import install

install()
if __name__ == "__main__":
    from vllm.entrypoints.cli.main import main
    main()
