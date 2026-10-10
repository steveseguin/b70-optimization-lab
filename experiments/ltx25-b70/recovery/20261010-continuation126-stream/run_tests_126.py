#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only recovery suites and children; refuses render-device opens and live sockets."""
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import unittest
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / 'data/resume-20261008/continuation126-tests/scratch'
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(SCRATCH)
tempfile.tempdir = str(SCRATCH)
os.environ.update(OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')

def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.realpath(os.fsdecode(args[0]))
        if path == '/dev/dri' or path.startswith('/dev/dri/'):
            raise RuntimeError('CPU runner refuses render-device opens')
    if event in ('os.kill', 'os.killpg'):
        raise RuntimeError('CPU runner refuses process signals')
    if event in ('socket.connect', 'socket.bind'):
        address = args[1]
        if isinstance(address, tuple) and (address[0] not in ('127.0.0.1', 'localhost', '::1') or address[1] == 8188):
            raise RuntimeError('CPU runner refuses live network')
sys.addaudithook(audit)

# Every child inherits the same protections before importing a test or torch.
original_popen = subprocess.Popen
class GuardedPopen(original_popen):
    def __init__(self, command, *args, **kwargs):
        if (isinstance(command, list) and len(command) >= 5 and command[:3] == ['git', '--no-replace-objects', '-C']
                and command[4] in ('rev-parse', 'ls-tree', 'show', 'cat-file')):
            super().__init__(command, *args, **kwargs)
            return
        if not (isinstance(command, list) and len(command) >= 3 and command[:2] == [sys.executable, '-B']):
            raise RuntimeError('CPU runner refuses unaudited child command')
        command = [sys.executable, '-B', str(HERE / 'run_tests_126.py'), '--child', *command[2:]]
        super().__init__(command, *args, **kwargs)
    def kill(self):
        raise RuntimeError('CPU runner never kills processes')
    def terminate(self):
        raise RuntimeError('CPU runner never terminates processes')
subprocess.Popen = GuardedPopen

if __name__ == '__main__':
    sys.path.insert(0, str(HERE))
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        target, rest = sys.argv[2], sys.argv[3:]
        if target == '-c':
            sys.argv = ['-c', *rest[1:]]
            exec(compile(rest[0], '<string>', 'exec'), {'__name__': '__main__'})
        else:
            sys.argv = [target, *rest]
            runpy.run_path(target, run_name='__main__')
    else:
        pattern = sys.argv[1] if len(sys.argv) > 1 else 'test_*.py'
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE), pattern=pattern))
        raise SystemExit(not result.wasSuccessful())
