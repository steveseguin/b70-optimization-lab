"""Derive service identity from the coordinator's actual command builder."""
import importlib.util
from pathlib import Path

LANEQUEUE = Path(__file__).resolve().parents[3] / 'ops/lane-queue/lanequeue.py'
spec = importlib.util.spec_from_file_location('p58ag_packet58ab_lanequeue', Path(__file__).with_name('coordinator_snapshot.py'))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def unit_name(job, library=''):
    command = L.command(job, '/tmp/packet58x-review.json', '/tmp/packet58x-exit.json', library)
    return next(arg.split('=', 1)[1] for arg in command if arg.startswith('--unit=')) + '.service'


def lane_unit_prefix():
    import json
    root=Path(__file__).resolve().parent.parent
    names=[json.loads((root/'proposals'/f'{kind}.json').read_text())['job_name'] for kind in ('smoke','v5')]
    # The caller also checks the complete service name, below.
    return 'screen-'+names[0].split('-smoke-')[0]+'-'

def allowed_units():
    import json
    root=Path(__file__).resolve().parent.parent
    return {unit_name(dict(name=json.loads((root/'proposals'/f'{kind}.json').read_text())['job_name'],lane='A',argv=[])) for kind in ('smoke','v5')}
