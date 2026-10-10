#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Bind133 client/launcher to the completed seal; verify all modern inner-plan pins."""
import ast
import hashlib
import json
from pathlib import Path
import pprint
import re

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
OUT = HERE / 'continuation133b-tests'
CLIENT = LANE / 'stream/ltx_continuation_client.py'
AUTHOR = LANE / 'recovery/20261010-continuation133b-stream'
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignments(text):
    for node in ast.parse(text).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == 'PACKETS':
            yield ast.literal_eval(target.slice), node


def main():
    seal = json.loads((OUT / 'seal.json').read_text())
    packet = Path(seal['packet'])
    assert sha(packet / 'manifest.json') == seal['manifest_sha256']
    plan = json.loads((packet / 'resolution/stream-plan.json').read_text())
    text = CLIENT.read_text()
    nodes = dict(assignments(text))
    previous = ast.literal_eval(nodes[133].value.args[0])
    names = list(previous['modules'])
    entry = dict(manifest_sha256=seal['manifest_sha256'], plan_sha256=plan['plan_sha256'],
                 modules={name: sha(packet / 'resolution/components' / (name + '.py')) for name in names},
                 reference_sha256=sha(packet / 'resolution/reference-frame-hashes.json'))
    replacement = ("PACKETS['133b'] = dict(" + pprint.pformat(entry, sort_dicts=False, width=100)
                   + ", dir=R / 'prepared-continuation-stream-133b')\n")
    lines = text.splitlines(keepends=True)
    node = nodes['133b']
    lines[node.lineno-1:node.end_lineno] = [replacement]
    CLIENT.write_text(''.join(lines))
    launch = AUTHOR / 'launch-133b.sh'
    source = launch.read_text()
    source, changed = re.subn(r'^MAN=(?:UNSEALED_PACKET_133B|[0-9a-f]{64})$',
                             'MAN=' + seal['manifest_sha256'], source, flags=re.MULTILINE)
    assert changed == 1
    launch.write_text(source)
    rows = []
    for number, node in assignments(CLIENT.read_text()):
        if number not in (120,121,122,123,'123b',124,125,126,127,128,129,130,131,132,133,'133b'):
            continue
        mapping = node.value if isinstance(node.value, ast.Dict) else node.value.args[0]
        pinned_plan = next(ast.literal_eval(v) for k, v in zip(mapping.keys, mapping.values)
                           if ast.literal_eval(k) == 'plan_sha256')
        path = ROOT / ('prepared-continuation-stream-' + str(number)) / 'resolution/stream-plan.json'
        inner = json.loads(path.read_text())['plan_sha256']
        assert pinned_plan == inner and pinned_plan != sha(path), number
        rows.append(dict(packet=number, inner_plan_sha256=inner, file_sha256=sha(path)))
    assert len(rows) == 16
    result = dict(all_pins_passed=True, packets=len(rows), assertions=2*len(rows), rows=rows,
                  packet133b_inner_plan_sha256=plan['plan_sha256'],
                  packet133b_manifest_sha256=seal['manifest_sha256'], client_sha256=sha(CLIENT))
    (OUT / 'client-pins.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
