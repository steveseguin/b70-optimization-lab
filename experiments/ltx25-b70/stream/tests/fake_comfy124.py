#!/usr/bin/env python3
"""Packet124 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy123b.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy123b.py')), 'exec'))
source = source.replace("assert c.PACKET == '123b'", 'assert c.PACKET == 124')
source = source.replace('stream123b-s', 'stream124-s')
source = source.replace("ap.add_argument('--aux-residency'", "ap.add_argument('--display-worker', choices=('serial', 'parallel'), default='serial')\nap.add_argument('--aux-residency'")
source = source.replace("SERVER_OPTIONS.update(run_write_allowance_bytes=", "SERVER_OPTIONS.update(display_worker=a.display_worker, run_write_allowance_bytes=")
# Model protocol chronology with real CPU fixture timestamps. The mock does not
# claim concurrent GPU work: it performs audio first on non-control parallel
# paths and emits the same auditable hand-off fields as packet124.
source = source.replace("                    if LEVERS[0] == 'cone':\n                        tm['display_start']", """                    if LEVERS[0] == 'cone':
                        if a.display_worker == 'parallel' and p['kind'] not in c.GATED_KINDS:
                            tm['audio_start_ns'] = time.time_ns()
                            time.sleep(0 if job.get('fast') else a.audio_delay)
                            tm['audio_done'] = time.time_ns()
                            tm['worker_queued_ns'] = time.time_ns()
                            tm['worker_start_ns'] = time.time_ns()
                        tm['display_start']""")
source = source.replace("            time.sleep(0 if job.get('fast') else a.audio_delay)\n            tm['audio_done'] = time.time_ns()", """            if 'audio_done' not in tm:
                time.sleep(0 if job.get('fast') else a.audio_delay)
                tm['audio_done'] = time.time_ns()""")
source = source.replace("'decode_done': t['audio_done']", "'decode_done': max(t['audio_done'], t.get('display_done', t['video_done']))")
source = source.replace("'server_options': dict(SERVER_OPTIONS), 'schema': sr.DECODE_SCHEMA,", """'display_worker': a.display_worker,
           'completion_worker': 'parallel' if a.display_worker == 'parallel' and p['kind'] not in c.GATED_KINDS else 'serial',
           'display_worker_timing': {'queued_ns': t.get('worker_queued_ns'),
                                    'start_ns': t.get('worker_start_ns'),
                                    'audio_start_ns': t.get('audio_start_ns'),
                                    'audio_done_ns': t['audio_done'] if 'audio_start_ns' in t else None,
                                    'gated_inline': p['kind'] in c.GATED_KINDS},
           'server_options': dict(SERVER_OPTIONS), 'schema': sr.DECODE_SCHEMA,""")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
