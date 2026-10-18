"""CPU-only checks of the separate build/output boundaries."""
from pathlib import Path
import pytest
import queue_runner as q
import window as w

from storage import B,REGISTERED_CHAIN
CHAIN=B/REGISTERED_CHAIN

def test_registered_chain_window_paths():
    assert q.admitted_output(CHAIN)==CHAIN
    for name in q.EARLY+q.LATE:
        if (CHAIN/name).exists():
            with pytest.raises((ValueError,RuntimeError,AssertionError)):
                w.output_path(CHAIN/name)
        else:
            assert w.output_path(CHAIN/name)==CHAIN/name
    for path in (CHAIN.parent/'unregistered',q.P/'build/unregistered'):
        with pytest.raises((ValueError,RuntimeError,AssertionError)):
            q.admitted_output(path)
        with pytest.raises((ValueError,RuntimeError,AssertionError)):
            w.output_path(path)
