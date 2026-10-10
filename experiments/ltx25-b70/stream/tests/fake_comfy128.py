#!/usr/bin/env python3
"""Packet128 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy127.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy127.py')), 'exec'))
source = source.replace('assert c.PACKET == 127', 'assert c.PACKET == 128')
source = source.replace('stream127-s', 'stream128-s')
source = source.replace("ap.add_argument('--snapshot-digest-cache'", "ap.add_argument('--maintenance-mode', choices=('parent', 'idle'), default='parent')\nap.add_argument('--snapshot-digest-cache'")
source = source.replace("SERVER_OPTIONS.update(snapshot_digest_cache=", "SERVER_OPTIONS.update(maintenance_mode=a.maintenance_mode, snapshot_digest_cache=")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
