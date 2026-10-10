#!/usr/bin/env python3
"""123b synthetic CPU protocol, no model operations."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy123.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy123.py')), 'exec'))
source = source.replace('assert c.PACKET == 123', "assert c.PACKET == '123b'")
source = source.replace('stream123-s', 'stream123b-s')
source = source.replace("ap.add_argument('--aux-residency'", "ap.add_argument('--run-write-allowance-gib', type=int, default=3)\nap.add_argument('--storage-refused', action='store_true')\nap.add_argument('--aux-residency'")
source = source.replace("    return classify(body['prompt'])", "    if a.storage_refused and S['phase'] == 'stream':\n        raise Refusal('storage', 'Stream storage allowance exhausted (50 GiB reserve, 3 GiB run allowance)')\n    return classify(body['prompt'])")
source = source.replace("SERVER_OPTIONS.update(aux_residency=", "SERVER_OPTIONS.update(run_write_allowance_bytes=a.run_write_allowance_gib * 2**30, aux_residency=")
source = source.replace("'storage': {}", "'storage': {'allowance_bytes': a.run_write_allowance_gib * 2**30, 'accounting': 'run-owned-st_blocks-v1'}")
source = source.replace("'storage': {'free_bytes':", "'storage': {'allowance_bytes': a.run_write_allowance_gib * 2**30, 'accounting': 'run-owned-st_blocks-v1', 'free_bytes':")
source = source.replace("'schema': sr.DECODE_SCHEMA,", "'server_options': dict(SERVER_OPTIONS), 'schema': sr.DECODE_SCHEMA,")
source = source.replace("'schema': sr.PREVIEW_SCHEMA,", "'server_options': dict(SERVER_OPTIONS), 'schema': sr.PREVIEW_SCHEMA,")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
