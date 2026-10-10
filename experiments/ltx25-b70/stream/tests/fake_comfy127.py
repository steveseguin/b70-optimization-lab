#!/usr/bin/env python3
"""Packet127 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy126.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy126.py')), 'exec'))
source = source.replace('assert c.PACKET == 126', 'assert c.PACKET == 127')
source = source.replace('stream126-s', 'stream127-s')
source = source.replace("ap.add_argument('--storage-scan-mode'", "ap.add_argument('--snapshot-digest-cache', type=int, choices=(0, 1), default=0)\nap.add_argument('--storage-scan-mode'")
source = source.replace("SERVER_OPTIONS.update(storage_scan_mode=", "SERVER_OPTIONS.update(snapshot_digest_cache=a.snapshot_digest_cache, storage_scan_mode=")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
