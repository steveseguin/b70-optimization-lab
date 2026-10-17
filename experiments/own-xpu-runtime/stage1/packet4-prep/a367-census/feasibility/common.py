"""Small, standard-library-only helpers. Importing this module never imports torch."""
import argparse
import json
import os
from pathlib import Path
import threading
import time


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


class Stages:
    def __init__(self, root, rank=0):
        self.root, self.rank = Path(root), rank
        self.lock = threading.Lock()
        self.stage, self.since = 'starting', time.monotonic()
        self.closed = threading.Event()
        self.mark('starting')
        threading.Thread(target=self.watch, daemon=True).start()

    def emit(self, event, **extra):
        row = dict(event=event, rank=self.rank, pid=os.getpid(),
                   unix_s=time.time(), monotonic_s=time.monotonic(), **extra)
        with (self.root / f'rank-{self.rank}.jsonl').open('a') as handle:
            handle.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)

    def mark(self, stage):
        with self.lock:
            self.stage, self.since = stage, time.monotonic()
            self.emit('stage', stage=stage)

    def watch(self):
        reported = None
        while not self.closed.wait(.5):
            with self.lock:
                age = time.monotonic() - self.since
                key = (self.stage, self.since)
                if age >= 120 and key != reported:
                    print(f'STALL at stage {self.stage} rank {self.rank}: {age:.3f}s; waiting', flush=True)
                    self.emit('stall', stage=self.stage, seconds=age)
                    reported = key


def arguments(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--handshake', action='store_true')
    parser.add_argument('--create-after-resume', action='store_true',
                        help='CCL hypothesis reproduction: resume before PG creation')
    args = parser.parse_args()
    if args.create_after_resume and not args.handshake:
        parser.error('--create-after-resume requires --handshake')
    return args


def wait_file(path, root):
    while not path.exists():
        if (root / 'abort').exists():
            raise RuntimeError('cooperative stop requested; no process is killed')
        time.sleep(.05)


def ready_go(args, stages):
    stages.mark('ready')
    (args.output / f'ready-{stages.rank}').touch()
    if args.handshake:
        stages.mark('wait_go')
        wait_file(args.output / 'go', args.output)
    stages.mark('measurement')


def finished(args, stages, *, close=True):
    stages.mark('done')
    (args.output / f'done-{stages.rank}').touch()
    if args.handshake:
        stages.mark('wait_release')
        wait_file(args.output / 'release', args.output)
    stages.mark('exit' if close else 'pause_handshake_complete')
    if close:
        stages.closed.set()
