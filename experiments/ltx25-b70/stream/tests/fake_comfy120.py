#!/usr/bin/env python3
"""CPU fake120 using119 fixtures; synthetic hashes are protocol tests only."""
from pathlib import Path

source = Path(__file__).with_name('fake_comfy119.py').read_text()
source = source.replace('assert c.PACKET == 119', 'assert c.PACKET == 120')
# Let fake119 finish its historical transformations, then add120 fields to the
# resulting fake118 source immediately before execution.
source = source[:source.index("# Preserve legacy fake118")]
exec(compile(source, str(Path(__file__).with_name('fake_comfy119.py')), 'exec'))
source = source.replace("ap.add_argument('--snapshot-mode'", "ap.add_argument('--display-device', choices=('xpu:3', 'xpu:2'), default='xpu:3')\nap.add_argument('--snapshot-mode'")
source = source.replace("'snapshot_schedule': a.snapshot_schedule}", "'snapshot_schedule': a.snapshot_schedule, 'display_device': a.display_device}")
source = source.replace("PLAN = hashlib.sha256(b'fake-plan-117').hexdigest()", "PLAN = '585d6da602b87cc3f8d1440a19255c91b458f326efb2b1d2e97d6cc752072031'")
source = source.replace("'device': 'xpu:3', 'order': 'fifo'", "'device': 'xpu:3', 'display_device': 'xpu:3' if p['kind'] == 'qualify-eager' else a.display_device, 'order': 'fifo'")
source = source.replace("'device': 'xpu:3', 'display_device':", "'display_replica': replica_record(job, images['images']['sha256']), 'device': 'xpu:3', 'display_device':")
source = source.replace('def make_decode_record(job, t):', """def replica_record(job, images_sha):
    if a.display_device != 'xpu:2':
        return None
    def budget(resident=0):
        free = 16 * 2**30
        transient, floor = 4 * 2**30, 2 * 2**30
        return {'free_bytes': free, 'new_resident_bytes': resident,
                'transient_budget_bytes': transient, 'floor_bytes': floor,
                'margin_bytes': free - resident - transient - floor}
    qualification = job['params']['kind'] != 'stream'
    residency = {'device': 'xpu:2', 'resident_bytes': 512 * 2**20, 'encoder_bytes': 0,
                 'graph_pool_bytes': 0, 'transient_budget_bytes': 4 * 2**30, 'floor_bytes': 2 * 2**30,
                 'before_install': budget(512 * 2**20), 'after_install': budget(), 'calls': 1,
                 'last_decode': {'before': budget(), 'after_free_bytes': 16 * 2**30, 'seconds': 0.01,
                                 'allocator_before': {'allocated': 1, 'reserved': 2, 'peak_allocated': 2},
                                 'allocator_after': {'allocated': 1, 'reserved': 2, 'peak_allocated': 2},
                                 'observed_peak_or_reservation_growth_bytes': 1,
                                 'peak_is_device_global_not_reset': True},
                 'weight_copy_bitwise_equal': True, 'native_seed': 0, 'dtype': 'torch.bfloat16',
                 'single_decode_thread': True}
    record = {'device': 'xpu:2', 'reference_device': 'xpu:3', 'mode': 'eager-uncached',
              'equal': True if qualification else None, 'residency': residency}
    if qualification:
        record.update(images_sha256=images_sha, reference_images_sha256=images_sha)
    return record


def make_decode_record(job, t):""")
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
