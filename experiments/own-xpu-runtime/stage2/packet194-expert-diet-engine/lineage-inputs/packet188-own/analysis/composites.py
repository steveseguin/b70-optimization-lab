#!/usr/bin/env python3
"""Composite prices on the V3 line (same replay as price_v3_levers.py) and the rank-0 A envelope (CPU-only, read-only)."""
import importlib.util, io, contextlib, json, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pv', HERE / 'price_v3_levers.py')
pv = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(pv)
T, gain, ROWS = pv.T, pv.gain, pv.ROWS
RT = pv.RT
def comp(x, k3=False, head=0.0, d=0.0, kio=False, a=0.0):
    Bd = x['Bd'] + (pv.C0_BD if k3 else 0.0); B = x['B'] - (pv.S1 if k3 else 0.0) - head; A = x['A'] - a
    D = x['D'] - (d if x['hit'] else 0.0); C = x['C']
    if kio:
        Bd -= RT; B -= 3 * RT; A -= RT
        if x['hit']: D -= 2 * RT
        else: C -= 2 * RT
    return T(x, D=D, Bd=Bd, B=B, A=A, C=C)
cases = {
 'k3 + kernel I/O central': dict(k3=True, kio=True),
 'k3 + head-transpose 0.177': dict(k3=True, head=0.177),
 'k3 + rank-0 A trim 0.105 (needed)': dict(k3=True, a=0.105),
 'k3 + rank-0 A trim 0.105 + kernel I/O': dict(k3=True, a=0.105, kio=True),
 'k2 + head-transpose 0.177 + kernel I/O': dict(head=0.177, kio=True),
 'k2 + head-transpose 0.177 + draft gaps 20% (0.096) + kernel I/O': dict(head=0.177, d=0.096, kio=True),
 'k2 + head-transpose 0.384 (100% micro)': dict(head=0.384),
 'k2 + draft gaps 0.19 (host batching ceiling) + head 0.177': dict(head=0.177, d=0.19),
}
out = {k: round(gain(lambda x, v=v: comp(x, **v)), 3) for k, v in cases.items()}
# rank-0 A envelope: A (op1 speculative command span) minus the engine's own half_completion_ms for that position
P = pv.rv.P187 / 'repeat-1'
env = []
for d in sorted(P.iterdir()):
    tj = d / 'rank0/timings.jsonl'
    if not tj.is_file():
        continue
    r = json.loads((d / 'receipt.json').read_text())
    spec_rows = {}
    for line in tj.read_text().splitlines():
        if line.strip():
            t = json.loads(line)
            if t.get('speculative'):
                spec_rows[t['position']] = t
    for t in r['rank_trace']:
        if t['rank'] == 0 and t['op'] == 1 and t['speculative'] and t['position'] in spec_rows:
            s = spec_rows[t['position']]
            env.append(dict(A=1000 * (t['rank_completed'] - t['rank_received']), half=s['half_completion_ms'], prepare=s['prepare_ms'], retire=s['p76_retirement_ms']))
out['rank0_A_envelope'] = dict(n=len(env), A=st.mean(e['A'] for e in env), half_completion=st.mean(e['half'] for e in env),
                               A_minus_half=st.mean(e['A'] - e['half'] for e in env), prepare_ms=st.mean(e['prepare'] for e in env),
                               p76_retirement_ms=st.mean(e['retire'] for e in env))
(HERE / 'composites-output.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

# ---- second block: ledger items re-priced on V3 (appended) ----
extra = {
 'p137 token-input path, D -0.044/hit (low projection)': gain(lambda x: T(x, D=x['D'] - 0.044) if x['hit'] else T(x)),
 'p137 token-input path, D -0.110/hit (packet158 input/embedding gap)': gain(lambda x: T(x, D=x['D'] - 0.110) if x['hit'] else T(x)),
 'packet160 free draft-head donation 0.471703 ms/hit (upper bound)': gain(lambda x: T(x, D=x['D'] - 0.471703) if x['hit'] else T(x)),
 'k3 + kernel I/O + p137 (D -0.110)': gain(lambda x: comp(dict(x, D=x['D'] - (0.110 if x['hit'] else 0.0)), k3=True, kio=True)),
 'k3 + kernel I/O + rank-0 prepare 0.096 off A': gain(lambda x: comp(x, k3=True, kio=True, a=0.096)),
}
out2 = {k: round(v, 3) for k, v in extra.items()}
print(json.dumps(out2, indent=1))
data = json.loads((HERE / 'composites-output.json').read_text()); data['ledger_reprices'] = out2
(HERE / 'composites-output.json').write_text(json.dumps(data, indent=1))
