#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Run historical client suites using cooperative, CPU-only fake children.

No OS process signals are sent. Fake outage tests pause request handling or call
HTTPServer.shutdown(); crash recovery asks the child client to exit at its next
Python trace event, preserving interrupted state without a process kill. This
covers interrupted-state recovery, not operating-system SIGKILL behavior.
All sockets are restricted to loopback test ports; port 8188 is blocked even in
argument-only tests. Every child uses this interpreter with -B. Outputs and IPC
stay in a newly created temporary directory.

Usage: /home/steve/.venvs/ltx25-baseline/bin/python -B run_cpu_suites.py run_tests_118b.py
"""
import http.server
import os
from pathlib import Path
import runpy
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
# Keep CPU fixtures within the coordinator's current two-thread budget.
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'
HERE = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/stream/tests')
SCRATCH = Path(__file__).resolve().parents[2] / 'data/resume-20261008/continuation134-tests/client-scratch'
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(SCRATCH)
tempfile.tempdir = str(SCRATCH)


def guard_device_opens():
    """Refuse render-device access before mocks or imported test code can open it."""
    def audit(event, args):
        if event != 'open' or not args:
            return
        path = args[0]
        if isinstance(path, (str, bytes, os.PathLike)):
            real = os.path.realpath(os.fsdecode(path))
            if real == '/dev/dri' or real.startswith('/dev/dri/'):
                raise RuntimeError('CPU suite refused device open: ' + real)
    sys.addaudithook(audit)


guard_device_opens()


def guard_sockets():
    original_connect = socket.socket.connect
    original_bind = socket.socket.bind
    def checked(action):
        def wrapped(sock, address):
            if isinstance(address, tuple):
                host, port = address[:2]
                if host not in ('127.0.0.1', 'localhost', '::1') or port == 8188:
                    raise RuntimeError('CPU suite refused network address %r' % (address,))
                # Isolate packet134 CPU fakes from concurrent packet135 tests.
                # Check the original port first:8188 can never be remapped.
                if type(port) is int and 18000 <= port <= 18999:
                    address = (host, port + 4000, *address[2:])
            return action(sock, address)
        return wrapped
    socket.socket.connect = checked(original_connect)
    socket.socket.bind = checked(original_bind)


def child(control, target, arguments):
    guard_sockets()
    paused = threading.Event()
    paused.set()
    stopping = threading.Event()
    server = []
    handlers = {}
    original_signal = signal.signal
    def register(sig, handler):
        handlers[sig] = handler
        return original_signal(sig, handler)
    signal.signal = register
    original_serve = http.server.ThreadingHTTPServer.serve_forever
    def serve(srv, *args, **kwargs):
        server.append(srv)
        return original_serve(srv, *args, **kwargs)
    http.server.ThreadingHTTPServer.serve_forever = serve
    original_handle = http.server.BaseHTTPRequestHandler.handle_one_request
    def handle(self):
        paused.wait()
        return original_handle(self)
    http.server.BaseHTTPRequestHandler.handle_one_request = handle

    def watch():
        cursor = 0
        while not stopping.is_set():
            try:
                commands = Path(control).read_text().splitlines()
            except FileNotFoundError:
                commands = []
            for command in commands[cursor:]:
                if command == 'pause':
                    paused.clear()
                elif command == 'resume':
                    paused.set()
                elif command == 'interrupt' and callable(handlers.get(signal.SIGINT)):
                    handlers[signal.SIGINT](signal.SIGINT, None)
                elif command in ('interrupt', 'exit'):
                    paused.set()
                    if server:
                        server[0].shutdown()
                    else:
                        stopping.set()
            cursor = len(commands)
            time.sleep(0.01)
    threading.Thread(target=watch, daemon=True).start()
    # Fake servers exit through serve_forever returning. Client interrupted-state
    # tests exit cooperatively on their main thread, without writing final state.
    if Path(target).name == 'ltx_continuation_client.py':
        def trace(frame, event, arg):
            if frame.f_code.co_filename != target:
                return None
            if stopping.is_set():
                raise SystemExit(99)
            return trace
        sys.settrace(trace)
    sys.argv = [target] + arguments
    runpy.run_path(target, run_name='__main__')


def _suite(target, arguments):
    guard_sockets()
    control_root = Path(tempfile.mkdtemp(prefix='ltx-cpu-control-'))
    base_popen = subprocess.Popen
    children = []
    class CooperativePopen(base_popen):
        def __init__(self, cmd, *args, **kwargs):
            self.control = control_root / ('child-%d.jsonl' % time.time_ns())
            if isinstance(cmd, list) and len(cmd) >= 3 and cmd[0] == sys.executable and cmd[1] == '-B':
                cmd = [sys.executable, '-B', str(Path(__file__).resolve()), '--child', str(self.control)] + cmd[2:]
            else:
                raise RuntimeError('CPU suite refused an unaudited child command: %r' % (cmd,))
            child_env = dict(kwargs.get('env') or os.environ)
            child_env.update(OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
            kwargs['env'] = child_env
            super().__init__(cmd, *args, **kwargs)
            children.append(self)
        def command(self, value):
            if self.poll() is None:
                with self.control.open('a') as out:
                    out.write(value + '\n')
        def send_signal(self, sig):
            commands = {signal.SIGINT: 'interrupt', signal.SIGSTOP: 'pause', signal.SIGCONT: 'resume'}
            if sig not in commands:
                raise RuntimeError('CPU suite refused process signal %r' % sig)
            self.command(commands[sig])
        def cooperative_exit(self):
            self.command('exit')
        def kill(self):
            raise RuntimeError('CPU suite never kills a process')
        def terminate(self):
            raise RuntimeError('CPU suite never terminates a process')
    subprocess.Popen = CooperativePopen
    path = (HERE / target).resolve()
    if path.parent != HERE or not path.name.startswith('run_tests_'):
        raise SystemExit('supply a run_tests_*.py file in this directory')
    source = path.read_text().replace('.kill()', '.cooperative_exit()')
    # The 118 author tree now includes review fixes; legacy client pins bind the
    # withdrawn, immutable 118 packet. Read its modules without modifying it.
    source = source.replace(
        '/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118-stream',
        '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118/resolution/components')
    sys.argv = [str(path)] + arguments
    try:
        exec(compile(source, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})
    finally:
        for process in children:
            process.cooperative_exit()
        for process in children:
            process.wait(timeout=30)
        subprocess.Popen = base_popen


def suite(target, arguments):
    # Every historical suite and its child packet copy lives inside this owned
    # root. Remove it on success or failure once cooperative children have exited.
    old_tempdir = tempfile.tempdir
    old_tmpdir = os.environ.get('TMPDIR')
    with tempfile.TemporaryDirectory(prefix='ltx-cpu-suite-') as scratch:
        tempfile.tempdir = scratch
        os.environ['TMPDIR'] = scratch
        try:
            _suite(target, arguments)
        finally:
            tempfile.tempdir = old_tempdir
            if old_tmpdir is None:
                os.environ.pop('TMPDIR', None)
            else:
                os.environ['TMPDIR'] = old_tmpdir


if __name__ == '__main__':
    if sys.argv[1] == '--child':
        child(sys.argv[2], sys.argv[3], sys.argv[4:])
    else:
        suite(sys.argv[1], sys.argv[2:])
