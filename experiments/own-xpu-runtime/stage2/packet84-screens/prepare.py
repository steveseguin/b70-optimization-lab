"""CPU only: use packet84's preparation API; never change its active selection."""
import json
from config import HERE, PACKET, ROOT, VIEWS, ORDER, values, view, sha
from build_engine import limits, save
from prepare_packet import seal_view
from prepare_selections import main as verify_selections
from screen_seal_support import wrapper_seal

def main():
    limits()
    frozen = {p: sha(p) for p in PACKET.iterdir() if p.is_file()}
    parent = PACKET.parent / 'packet80-record-bundle'
    parent_choice = json.loads((parent / 'bundle-selection.json').read_text())
    for k, v in VIEWS['control'].items():
        if k not in ('recurrence', 'draft_head'):
            assert parent_choice[k] == v, ('packet80 baseline changed', k)
    assert parent_choice['placement'] == '1'
    for label in VIEWS:
        assert seal_view(values(label), '1') == view(label)
    old = json.loads((parent / 'selection.json').read_text())
    control = json.loads((view('control') / 'selection.json').read_text())
    for key in ('head_format', 'head_prefix'):
        assert control['draft'].pop(key) == 'production'
    assert control == old, 'control differs from packet80 beyond explicit production draft-head metadata'
    verify_selections()
    wrapper_seal()
    assert all(sha(p) == h for p, h in frozen.items()), 'packet84 root file changed'
    sources = [*HERE.glob('*.py'), parent / 'bundle-selection.json', parent / 'selection.json',
               PACKET / 'run_screen.py', PACKET / 'screen_plans.py',
               PACKET / 'prepare_selections.py', PACKET / 'screen_seal_support.py',
               PACKET / 'build-device-receipt.json', PACKET / 'build/full-shape/fixture']
    save(HERE / 'composition-pin.json', dict(passed=True, device_executed=False,
         views=VIEWS, order=list(ORDER), placement='1',
         binary_sha256=sha(PACKET / 'build/device/own-rt-iq3'),
         sources={str(p.relative_to(ROOT)): sha(p) for p in sources},
         seals={label: sha(view(label) / 'screen-seal.json') for label in VIEWS}))
    print('Three compositions sealed; packet84 active files unchanged')

if __name__ == '__main__':
    main()
