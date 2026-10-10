#!/usr/bin/env python3
"""CPU fake121 inherits fake120 protocol; synthetic bytes never prove GPU identity."""
from pathlib import Path

source = Path(__file__).with_name('fake_comfy120.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
source = source.replace("'assert c.PACKET == 120'", "'assert c.PACKET == 121'")
exec(compile(source, str(Path(__file__).with_name('fake_comfy120.py')), 'exec'))
source = source.replace('choices=(49, 97, 121)', 'choices=(49, 97, 121, 145)')
source = source.replace("'chunk_121': True,", "'chunk_121': True, 'chunk_145': True,")
source = source.replace('4 * 2**30', '(4 * 2**30 * (((a.frames - 1) // 8 + 1) ** 2) + 255) // 256')
source = source.replace('585d6da602b87cc3f8d1440a19255c91b458f326efb2b1d2e97d6cc752072031', '5c3aa526275b2e64e754b7c871cb4ce00f36d49888950df5f84d560b7727fd28')
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
