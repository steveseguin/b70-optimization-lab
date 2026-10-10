#!/usr/bin/env python3
"""Packet129 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy128.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy128.py')), 'exec'))
source = source.replace('assert c.PACKET == 128', 'assert c.PACKET == 129')
source = source.replace('stream128-s', 'stream129-s')
source = source.replace("'atomic_preview': True,", "'atomic_preview': True, 'atomic_evidence_publication': True,")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
