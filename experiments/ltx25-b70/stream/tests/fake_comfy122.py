#!/usr/bin/env python3
"""CPU fake122 inherits fake120 protocol; synthetic bytes never prove GPU identity."""
from pathlib import Path

source = Path(__file__).with_name('fake_comfy120.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
source = source.replace("'assert c.PACKET == 120'", "'assert c.PACKET == 122'")
exec(compile(source, str(Path(__file__).with_name('fake_comfy120.py')), 'exec'))
source = source.replace('choices=(49, 97, 121)', 'choices=(49, 97, 121, 145)')
source = source.replace("'chunk_121': True,", "'chunk_121': True, 'chunk_145': True,")
source = source.replace('4 * 2**30', '(4 * 2**30 * (((a.frames - 1) // 8 + 1) ** 2) + 255) // 256')
source = source.replace('585d6da602b87cc3f8d1440a19255c91b458f326efb2b1d2e97d6cc752072031', '0ef91a395112bd7d1ffecbbc2d74bf5ccc89267751447be9b21a4b4ec107c060')
source = source.replace("ap.add_argument('--display-device'", "ap.add_argument('--display-transient-gib')\nap.add_argument('--display-device'")
source = source.replace("'snapshot_schedule': a.snapshot_schedule, 'display_device': a.display_device}",
                        "'snapshot_schedule': a.snapshot_schedule, 'display_device': a.display_device}\nif a.display_transient_gib is not None:\n    from decimal import Decimal\n    SERVER_OPTIONS['display_replica_transient_budget_bytes'] = int(Decimal(a.display_transient_gib) * 2**30)")
source = source.replace('(4 * 2**30 * (((a.frames - 1) // 8 + 1) ** 2) + 255) // 256',
                        "SERVER_OPTIONS.get('display_replica_transient_budget_bytes', (4 * 2**30 * (((a.frames - 1) // 8 + 1) ** 2) + 255) // 256)")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
