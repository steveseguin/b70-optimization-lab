#!/usr/bin/env python3
"""Packet126 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy125.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy125.py')), 'exec'))
source = source.replace('assert c.PACKET == 125', 'assert c.PACKET == 126')
source = source.replace('stream125-s', 'stream126-s')
source = source.replace("ap.add_argument('--display-worker'", "ap.add_argument('--storage-scan-mode', choices=('request', 'background'), default='request')\nap.add_argument('--display-worker'")
source = source.replace("SERVER_OPTIONS.update(gc_interval_seconds=", "SERVER_OPTIONS.update(storage_scan_mode=a.storage_scan_mode, gc_interval_seconds=")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
