#!/usr/bin/env python3
"""CPU fake119: reuse fake118's HTTP fixture with explicit packet119 options.

Synthetic timings and hashes test protocol binding only, never performance or
GPU scheduling. Run only through run_cpu_suites.py (loopback guard, cooperative stop).
"""
from pathlib import Path

source = Path(__file__).with_name('fake_comfy118.py').read_text()
source = source.replace("assert c.PACKET in (118, '118b')", 'assert c.PACKET == 119')
source = source.replace("ap.add_argument('--snapshot-mode'", """ap.add_argument('--display-schedule', choices=('sampler-a', 'sampler-b', 'eager-display'), default='sampler-a')
ap.add_argument('--anchor-read-ahead', type=int, choices=(0, 1), default=0)
ap.add_argument('--snapshot-schedule', choices=('full', 'a-xpu3-sync'), default='full')
ap.add_argument('--snapshot-mode'""")
source = source.replace("SERVER_OPTIONS = {'snapshot_mode': a.snapshot_mode, 'decoder_graph_pool_cap_bytes': POOL_CAP}",
"""SERVER_OPTIONS = {'snapshot_mode': a.snapshot_mode, 'decoder_graph_pool_cap_bytes': POOL_CAP,
                  'display_schedule': a.display_schedule, 'anchor_read_ahead': a.anchor_read_ahead,
                  'snapshot_schedule': a.snapshot_schedule}""")
source = source.replace("'prep_ahead': LEVERS[2], 'snapshot_mode': a.snapshot_mode, 'decoder_graph_pool_cap_bytes': POOL_CAP,",
                        "'prep_ahead': LEVERS[2], **SERVER_OPTIONS,")
source = source.replace('def make_decode_record(job, t):', """_base_decoder_block = decoder_block

def decoder_block(job, images_sha):
    result = _base_decoder_block(job, images_sha)
    if a.display_schedule == 'eager-display' and a.decoder_graph and a.anchor == 'frame' and LEVERS[0] == 'cone':
        if result['new_captures']:
            result['new_captures'] = 1
        result['signatures']['forward_diff_step'] = 0
        if result.get('pool'):
            result['pool']['captured'] = ['forward_pre_diffusion'] if DG['captured'] else []
            result['pool']['capped'] = []
    return result


def make_decode_record(job, t):""")
source = source.replace("'server_options': dict(SERVER_OPTIONS),", """'server_options': dict(SERVER_OPTIONS),
            'anchor_read_source': 'verified-read-ahead' if a.anchor_read_ahead and anchored and kind != 'qualify-eager'
                                  else 'native',""")
source = source.replace("'parts_s': {}, 'min_margin_bytes': 2 ** 31", """'parts_s': {}, 'min_margin_bytes': 2 ** 31,
             'synchronized': ['xpu:3'] if a.snapshot_schedule == 'a-xpu3-sync' and not dual and kind == 'stream'
                             and label in ('A-before', 'A-after') else ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'],
             'memory_cards': ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3']""")
# Preserve legacy fake118 stats/ready filenames for its Env harness.
exec(compile(source, str(Path(__file__).with_name('fake_comfy118.py')), 'exec'))
