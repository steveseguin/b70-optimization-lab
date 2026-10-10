#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Packet131 synthetic CPU protocol. Admissions and bytes are fixtures, not GPU evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy130.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy130.py')), 'exec'))
source = source.replace('assert c.PACKET == 130', 'assert c.PACKET == 131')
source = source.replace('stream130-s', 'stream131-s')
source = source.replace("ap.add_argument('--maintenance-mode'", "ap.add_argument('--cone-graph-memory', choices=('off', 'replica-release'), default='off')\nap.add_argument('--maintenance-mode'")
source = source.replace("SERVER_OPTIONS.update(maintenance_mode=", "SERVER_OPTIONS.update(cone_graph_memory=a.cone_graph_memory, maintenance_mode=")
# The130 source already prefixed the maintenance update with allocator identity.
source = source.replace("SERVER_OPTIONS.update(display_allocator_release=", "SERVER_OPTIONS.update(cone_graph_memory=a.cone_graph_memory, display_allocator_release=")
source = source.replace("'atomic_evidence_publication': True,", "'atomic_evidence_publication': True, 'cone_graph_memory': True,")
source = source.replace('def make_decode_record(job, t):', '''def cone_admission(job):
    if a.cone_graph_memory == 'off' or job['params']['kind'] == 'qualify-eager':
        return None
    first = job['params']['kind'] == 'qualify-graph' and job['params']['chunk_index'] == 0
    gib = 2**30
    required = 9*gib + 3*gib//4 + (5*gib if first else 0)
    free = 20*gib
    return dict(schema='ltx.stream131.cone-memory.v1', mode='replica-release', first_capture=first,
                capture_reserve_bytes=5*gib if first else 0, floor_bytes=9*gib,
                screening_bytes=3*gib//4, required_bytes=required, free_bytes=free,
                margin_bytes=free-required, reserve_is_measured=False,
                allocator_release=dict(schema='ltx.stream130.allocator-release.v1', mode='before-admission',
                    scope='process-wide XPU allocator', reclaim_is_not_guaranteed=True,required_bytes=required, phase='before-cone',
                    admission_free_before_bytes=free, admission_free_after_bytes=free, release_called=False))


def make_decode_record(job, t):''')
source = source.replace("'display_worker': a.display_worker,", "'cone_graph_memory_admission': cone_admission(job), 'display_worker': a.display_worker,")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
