"""Fixed packet65 job-file parser and argv; no device operations."""
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from common import HERE, require, read

QUICK = Path(__file__).resolve().parent
P = HERE.parent
ORDERS = {'A': ('production', 'wide64', 'wg64', 'wg128', 'prefetch64', 'production'),
          'B': ('production', 'prefetch64', 'wg128', 'wg64', 'wide64', 'production')}


def jobs(path, lane):
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split('|')
        require(len(parts) == 6, 'job needs out|lineage|seal|binary|dispatch|placement')
        out, lineage, seal, binary, dispatch, placement = parts
        root = Path(lineage).resolve()
        choice = root.name
        require(root == P / 'selections' / choice and choice in ORDERS[lane], 'foreign selection')
        require(Path(seal).resolve() == root / 'screen-seal.json'
                and Path(binary).absolute() == root / 'build/device/own-rt-iq3'
                and Path(dispatch).resolve() == root / 'dispatch-speed6.json'
                and placement == '1', 'job identity differs')
        require(Path(out).name == out and out.startswith('p65-quick-' + lane + '-'), 'invalid output name')
        rows.append(dict(out=out, choice=choice, lineage=lineage, seal=seal, binary=binary,
                         dispatch=dispatch, placement=placement))
    require(tuple(r['choice'] for r in rows) == ORDERS[lane], 'fixed six-screen order required')
    require(len({r['out'] for r in rows}) == 6, 'duplicate screen output')
    return rows


def command(row, lane, review=None, plan=False):
    cmd = ['/usr/bin/python3', '-B', str(QUICK / 'screen.py'), '--profile', 'tp2',
           '--lane', lane, '--timing', 'token', '--placement', '1']
    for key in ('lineage', 'seal', 'binary', 'dispatch'):
        cmd += ['--' + key, row[key]]
    cmd += ['--output', str(HERE / 'evidence' / row['out'])]
    return cmd + (['--plan'] if plan else ['--fault-review', str(review), '--authorized-device-window'])
