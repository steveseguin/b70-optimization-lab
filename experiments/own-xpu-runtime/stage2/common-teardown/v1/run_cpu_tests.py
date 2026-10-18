#!/usr/bin/env python3
"""Run the regressions with writes restricted to scratch and no subprocesses."""
import os
from pathlib import Path
import sys
import tempfile
import unittest


def main():
    sys.dont_write_bytecode = True
    with tempfile.TemporaryDirectory(prefix='teardown-cpu-suite-') as directory:
        root = Path(directory).resolve()
        tempfile.tempdir = str(root)

        def writable(path, dir_fd=None):
            if isinstance(path, int):
                # Existing stdout/stderr are fine. Files opened by tests already
                # passed this guard; a new fd cannot open a device on its own.
                return
            path = Path(os.fsdecode(path))
            if not path.is_absolute() and dir_fd is not None and dir_fd != -1:
                path = Path(os.readlink('/proc/self/fd/' + str(dir_fd))) / path
            # Resolve the parent, not a symlink being removed inside scratch.
            resolved = path.parent.resolve() / path.name
            if resolved != root and root not in resolved.parents:
                raise PermissionError('test write outside scratch: ' + str(resolved))

        def audit(event, args):
            if event == 'open':
                path, mode, flags = args
                if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                    writable(path)
                    if not isinstance(path, int) and Path(path).is_symlink():
                        writable(Path(path).resolve())
            elif event in ('os.remove', 'os.rmdir'):
                writable(args[0], args[1])
            elif event == 'os.mkdir':
                writable(args[0], args[2])
            elif event == 'os.rename':
                writable(args[0], args[2])
                writable(args[1], args[3])
            elif event == 'os.symlink':
                writable(args[1], args[2])
            elif event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn',
                           'os.kill', 'os.killpg', 'socket.connect', 'ctypes.dlopen'):
                raise PermissionError('CPU test forbids ' + event)

        sys.addaudithook(audit)
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_*.py')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
