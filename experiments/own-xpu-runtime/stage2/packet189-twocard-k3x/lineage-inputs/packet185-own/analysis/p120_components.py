import ast, json, statistics as st, sys
from pathlib import Path
S=Path('experiments/own-xpu-runtime/stage2')
method=(S/'packet126-early-draft/method/p85_model.py').read_bytes()
tree=ast.parse(method); scope={}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('duration','intervals')],type_ignores=[]),'m','exec'),scope)
def comps(run):
    rows=[]
    for p in sorted(run.glob('*/receipt.json')):
        r=json.loads(p.read_text())
        if 'prompt_class' not in r: continue
        try: iv=scope['intervals'](r)
        except Exception as e: print('skip',p,e); continue
        rows+=iv
    out={}
    for hit in (True,False):
        rr=[r for r in rows if r['hit']==hit]
        out['hit' if hit else 'miss']={'n':len(rr),**{k:round(st.mean(r[k] for r in rr),4) for k in ['D','R','C','A','B','spec_start_offset_ms','unresolved_control_gaps_ms','elapsed_ms']}}
    return out
for name in sys.argv[1:]:
    print(name, json.dumps(comps(Path(name)),indent=0))
