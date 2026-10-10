#!/usr/bin/env python3
"""Run historical client suites using cooperative, CPU-only fake children.

No OS process signals are sent. Fake outage tests pause request handling or call
HTTPServer.shutdown(); crash recovery asks the child client to exit at its next
Python trace event, preserving interrupted state without a process kill. This
covers interrupted-state recovery, not operating-system SIGKILL behavior.
All sockets are restricted to loopback test ports; port 8188 is blocked even in
argument-only tests. Every child uses this interpreter with -B. Outputs and IPC
stay in a newly created temporary directory.

Usage: /home/steve/.venvs/ltx25-baseline/bin/python3 -B run_cpu_suites.py run_tests_118b.py
"""
import http.server
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
HERE = Path(__file__).resolve().parent


def guard_sockets():
    original_connect = socket.socket.connect
    original_bind = socket.socket.bind
    def checked(action):
        def wrapped(sock, address):
            if isinstance(address, tuple):
                host, port = address[:2]
                if host not in ('127.0.0.1', 'localhost', '::1') or port == 8188:
                    raise RuntimeError('CPU suite refused network address %r' % (address,))
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


def suite(target, arguments):
    guard_sockets()
    control_root = Path(tempfile.mkdtemp(prefix='ltx-cpu-control-'))
    base_popen = subprocess.Popen
    class CooperativePopen(base_popen):
        def __init__(self, cmd, *args, **kwargs):
            self.control = control_root / ('child-%d.jsonl' % time.time_ns())
            if isinstance(cmd, list) and len(cmd) >= 3 and cmd[0] == sys.executable and cmd[1] == '-B':
                cmd = [sys.executable, '-B', str(Path(__file__).resolve()), '--child', str(self.control)] + cmd[2:]
            else:
                raise RuntimeError('CPU suite refused an unaudited child command: %r' % (cmd,))
            super().__init__(cmd, *args, **kwargs)
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
    exec(compile(source, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})


if __name__ == '__main__':
    if sys.argv[1] == '--child':
        child(sys.argv[2], sys.argv[3], sys.argv[4:])
    else:
        suite(sys.argv[1], sys.argv[2:])
