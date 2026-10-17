"""CPU-only post-device selection; independently replay both packet54 owners."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from storage import digest

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
P54 = P.parent / 'packet54-compute'
BANKED = P.parent / 'packet53b-virtual/evidence-copy/p53b-a-summary.json'
BANKED_SHA = '8c20eddf341b541c90b87f4b4dbea521cacec8a6fff6220b853ebdd3ae0b94ef'
P54_SEAL_SHA = 'c27ecf935060a2e59a9acb9615be447e32f7881c9a886687a4b9f75dc5d0f508'
CHOICES = {'route': ('production', 'route-rank4', 'route-exp32-rank4'),
           'recurrence': ('production', 'rows4-shared', 'rows8-shared'),
           'hc': ('production', 'mix-vector4')}
CLASS_MAP = {'route': 'route', 'recurrence': 'gdn.recurrence', 'hc': 'hc.inject_mix_norm'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def validate_choices(value):
    require(isinstance(value, dict) and set(value) == set(CHOICES), 'selection must name exactly route/recurrence/hc')
    for cls, choice in value.items():
        require(isinstance(choice, str) and choice in CHOICES[cls], 'unregistered selection: ' + cls)
    return value


def replay(windows):
    require(len(windows) == 2 and len({str(Path(p).resolve()) for p in windows}) == 2,
            'two distinct packet54 timing owners required')
    require(digest(P54 / 'seal.json') == P54_SEAL_SHA, 'packet54 seal changed')
    source_pins = json.loads((P54 / 'seal.json').read_text())['sources']
    require(source_pins and str((P54 / 'summarize.py').relative_to(ROOT)) in source_pins,
            'packet54 verifier missing from sealed sources')
    for name, expected in source_pins.items():
        require(digest(ROOT / name) == expected, 'packet54 source changed: ' + name)
    # A separate Python namespace prevents same-named packet helper imports from
    # resolving to49d. This command only hashes and parses existing receipts.
    code = ('import json,sys;sys.path.insert(0,sys.argv[1]);'
            'from summarize import fresh_pair;print(json.dumps(fresh_pair(sys.argv[2:])))')
    run = subprocess.run([sys.executable, '-B', '-c', code, str(P54), *map(str, windows)],
                         capture_output=True, text=True, check=True, timeout=480)
    return json.loads(run.stdout)


def decision_choices(decision):
    require(decision.get('schema') == 'own-runtime.packet54.two-owner-timing.v1'
            and decision.get('passed') is True and decision.get('device_executed') is True,
            'not a validated packet54 decision')
    require(digest(BANKED) == BANKED_SHA, 'banked packet53b evidence changed')
    banked = json.loads(BANKED.read_text())
    selected = {}
    savings = [0., 0.]
    for cls, source in CLASS_MAP.items():
        item = decision['selected_classes'][source]
        choice = 'production' if item['variant'] == 'control' else item['variant']
        selected[cls] = choice
        values = item['owner_saved_us']
        require(len(values) == 2 and all(type(x) in (int, float) and math.isfinite(x) for x in values),
                'invalid owner savings')
        if choice == 'production':
            require(values == [0, 0], 'production cannot claim savings')
        savings = [a + b for a, b in zip(savings, values)]
    validate_choices(selected)
    require(decision['selected_classes']['ffn.combine']['variant'] == 'control', 'closed FFN candidate selected')
    require(savings == decision['owner_saved_us'], 'selected savings do not sum to decision')
    banked_values = banked['owner_saved_us']
    combined = [a + b for a, b in zip(banked_values, savings)]
    require(len(combined) == 2 and all(x >= 40 for x in combined),
            'banked plus selected savings must reach40 microseconds in BOTH owners')
    require(decision['banked_p53b_owner_us'] == banked_values
            and decision['combined_owner_us'] == combined
            and decision['integration_threshold_us'] == 40 and decision['packet49d_trigger'] is True,
            'packet54 combined decision differs')
    return selected, combined


def verify_selection():
    row = json.loads((P / 'selection.json').read_text())
    require(set(row) == {'schema', 'choices', 'decision'} and row['schema'] == 'packet49d.selection.v1',
            'selection schema differs')
    validate_choices(row['choices'])
    binding = row['decision']
    require(isinstance(binding, dict), 'selection pending packet54 device decision')
    require(binding['path'] == 'selection-decision.json', 'selection decision must be packet-local')
    source = P / binding['path']
    require(digest(source) == binding['sha256'], 'selection decision changed')
    decision = json.loads(source.read_text())
    observed = replay(decision['windows'])
    require(decision == observed, 'selection decision differs from verified device receipts')
    choices, combined = decision_choices(observed)
    require(row['choices'] == choices, 'selection differs from common packet54 decision')
    return dict(selection_sha256=digest(P / 'selection.json'), decision_sha256=digest(source),
                choices=choices, combined_owner_us=combined, threshold_us=40,
                banked_evidence_sha256=BANKED_SHA, packet54_seal_sha256=P54_SEAL_SHA,
                timing_windows=[{'path': w, 'sha256': digest(Path(w))} for w in observed['windows']])


def write_selection(windows):
    require(not (P / 'build-receipt.json').exists(), 'final packet seal already exists; never edit a sealed selection')
    require(not (P / 'build/device-cards01-a').exists(), 'device chain already exists')
    decision = replay(windows)
    choices, combined = decision_choices(decision)
    dest = P / 'selection-decision.json'
    require(not dest.exists(), 'selection decision already recorded')
    dest.write_text(json.dumps(decision, indent=2) + '\n')
    row = dict(schema='packet49d.selection.v1', choices=choices,
               decision={'path': dest.name, 'sha256': digest(dest)})
    temporary = P / 'selection.json.tmp'
    temporary.write_text(json.dumps(row, indent=2) + '\n')
    temporary.replace(P / 'selection.json')
    return dict(choices=choices, combined_owner_us=combined, device_executed=False)


def main():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity differs')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows', nargs=2, type=Path)
    args = parser.parse_args()
    print(json.dumps(write_selection(args.windows) if args.windows else verify_selection(), indent=2))


if __name__ == '__main__':
    main()
