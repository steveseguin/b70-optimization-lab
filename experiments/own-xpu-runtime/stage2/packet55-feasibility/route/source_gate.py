#!/usr/bin/env python3
"""Bind real project include closures, including injected headers outside mirror."""
import argparse,hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4]
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def closure(commands):
    all_paths=set()
    for argv in commands:
        includes=[Path(a[2:]).resolve() for a in argv if a.startswith('-I')]
        pending=[Path(argv[-1])];seen=set()
        while pending:
            path=pending.pop().resolve()
            if path in seen:continue
            seen.add(path);all_paths.add(path)
            for bracket,name in re.findall(r'^\s*#include\s*(["<])([^"\n>]+)[">]',path.read_text(),re.M):
                options=[Path(name)] if Path(name).is_absolute() else ([path.parent/name] if bracket=='"' else [])+[i/name for i in includes]
                target=next((p.resolve() for p in options if p.is_file()),None)
                if target is not None and target.is_relative_to(ROOT):pending.append(target)
                elif bracket=='"':raise ValueError('unresolved project include:'+name)
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(all_paths)}
def make():
    rows={}
    for mode in ('device','gnu-host'):
        path=P/'build'/mode/'build-receipt.json';record=json.loads(path.read_text())
        rows[mode]=dict(binary_sha256=sha(P/'build'/mode/'own-rt-iq3'),receipt_sha256=sha(path),
                        dependencies_sha256=closure(record['commands']))
        assert rows[mode]['binary_sha256']==record['binary_sha256']
        assert all(sha(P/name)==value for name,value in record['overlay_sha256'].items())
    base=P.parents[1]/'packet49c-round2';parent=json.loads((base/'build-device-receipt.json').read_text())
    guard=str((base/'kernel_guard.hpp').relative_to(ROOT))
    assert rows['device']['dependencies_sha256'][guard]==parent['compiled_sources_sha256'][guard]
    scripts=['build.py','build_host.py','route_hook.inc','source_gate.py','window.py','convert.py','prepare_inputs.py','calibration-prompts.json','cpu_smoke.py','test_route.py']
    result=dict(schema='packet55.route-source-closure.v1',passed=True,device_executed=False,modes=rows,
                parent_device_receipt_sha256=sha(base/'build-device-receipt.json'),
                tooling_sha256={name:sha(P/name) for name in scripts},
                inputs_sha256={str(path.relative_to(P)):sha(path) for path in [P/'build/calibration-tokenized.json',*(P/'build/input'/name for name in ('input.json','plan.tsv','identity.tsv','tokens.txt','vocab.bin'))]})
    (P/'source-closure.json').write_text(json.dumps(result,indent=2)+'\n');return result

def check():
    row=json.loads((P/'source-closure.json').read_text());assert row['passed'] and not row['device_executed']
    for name,digest in row['tooling_sha256'].items():assert sha(P/name)==digest,'tooling changed:'+name
    for name,digest in row['inputs_sha256'].items():assert sha(P/name)==digest,'input changed:'+name
    for mode,r in row['modes'].items():
        assert sha(P/'build'/mode/'own-rt-iq3')==r['binary_sha256'],'binary changed'
        assert sha(P/'build'/mode/'build-receipt.json')==r['receipt_sha256'],'build receipt changed'
        for name,digest in r['dependencies_sha256'].items():assert sha(ROOT/name)==digest,'include changed:'+name
    return row
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
    r=make() if a.write else check();print(json.dumps(dict(passed=True,device_executed=False,dependencies={k:len(v['dependencies_sha256']) for k,v in r['modes'].items()})))
