#!/usr/bin/env python3
"""Packet125 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy124.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy124.py')), 'exec'))
source = source.replace('assert c.PACKET == 124', 'assert c.PACKET == 125')
source = source.replace('stream124-s', 'stream125-s')
source = source.replace("ap.add_argument('--display-worker'", "ap.add_argument('--gc-interval-seconds', type=int, choices=(10, 60), default=10)\nap.add_argument('--display-worker'")
source = source.replace("SERVER_OPTIONS.update(display_worker=", "SERVER_OPTIONS.update(gc_interval_seconds=a.gc_interval_seconds, display_worker=")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
