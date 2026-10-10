#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Packet130 synthetic CPU protocol; no numerical or performance evidence."""
from pathlib import Path
source = Path(__file__).with_name('fake_comfy129.py').read_text()
source = source[:source.rindex("exec(compile(source,")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy129.py')), 'exec'))
source = source.replace('assert c.PACKET == 129', 'assert c.PACKET == 130')
source = source.replace('stream129-s', 'stream130-s')
source = source.replace("ap.add_argument('--maintenance-mode'", "ap.add_argument('--display-allocator-release', choices=('off', 'before-admission'), default='off')\nap.add_argument('--maintenance-mode'")
source = source.replace("SERVER_OPTIONS.update(maintenance_mode=", "SERVER_OPTIONS.update(display_allocator_release=a.display_allocator_release, maintenance_mode=")
# Synthetic no-release admissions: free memory was sufficient. These are
# protocol fixtures, never measured allocation or reclaim evidence.
source = source.replace("    record = {'device': 'xpu:2', 'reference_device':", """    if a.display_allocator_release == 'before-admission':
        for phase, admission in (
                ('before-install', residency['before_install']),
                ('after-install', residency['after_install']),
                ('before-decode', residency['last_decode']['before'])):
            admission['allocator_release'] = dict(
                schema='ltx.stream130.allocator-release.v1', mode='before-admission', phase=phase,
                required_bytes=admission['new_resident_bytes'] + admission['transient_budget_bytes']
                               + admission['floor_bytes'] + 3 * 2**28,
                admission_free_before_bytes=admission['free_bytes'],
                admission_free_after_bytes=admission['free_bytes'], release_called=False,
                scope='process-wide XPU allocator', reclaim_is_not_guaranteed=True)
    record = {'device': 'xpu:2', 'reference_device':""")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
