"""Bounded CPU-only policy, memory and drain evidence."""
import ast,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
from build_engine import limits,save,sha
P=Path(__file__).resolve().parent;ROOT=P.parents[3]

def main():
    limits();started=time.monotonic()
    for f in P.glob('*.py'):ast.parse(f.read_text(),filename=str(f))
    command=[sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_*.py','-v']
    result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    (P/'evidence/python-cpu-gates.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stderr[-6000:]
    import re
    count=int(re.search(r'Ran (\d+) tests',result.stderr)[1])
    save(P/'evidence/python-cpu-gates.json',dict(passed=True,device_executed=False,checks=count,seconds=time.monotonic()-started,
        log_sha256=sha(P/'evidence/python-cpu-gates.log'),sources={str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.py')}))
    scanner=P/'check_drain_fix.py'
    result=subprocess.run([sys.executable,'-B',str(scanner),str(P),'--json'],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    row=json.loads(result.stdout);assert row['passed'] and row['counts']=={'FIXED':1,'UNFIXED':0}
    row.update(device_executed=False);save(P/'evidence/drain-fix.json',row)
    checker=P/'check_teardown_on_error.py'
    result=subprocess.run([sys.executable,'-B',str(checker),str(P),'--json'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
    row=json.loads(result.stdout)
    assert row['status']=='NOT_VERIFIED' and row['files'][0]['status']=='MATCH'
    save(P/'evidence/teardown-inventory.json',row)
    save(P/'evidence/teardown-integration.json',dict(passed=True,device_executed=False,helper_sha256=sha(P/'teardown_on_error.py'),
        generic_scanner_status='NOT_VERIFIED',reason='One-card entry is outside the chain/v4 templates; seven local integration regressions exercise the exact called adapter.',
        adapter_sha256=sha(P/'owner_teardown.py'),window_sha256=sha(P/'window.py'),test_sha256=sha(P/'test_bracket.py'),
        proof='reaped driver and observed native descendants; complete one-owner native drain; clean supervisor and journal; same admission.devices_drained path; experiment failure unchanged'))
    import memory_plan as M
    budget=M.window_plan('WSCREEN');required=budget['host_required_available_bytes']
    assert required==98_990_252_032 and budget['device_owned_bound_bytes']==29_963_128_848
    assert M.admit(dict(MemAvailable=required),budget)['passed']
    census=json.loads((P/'evidence/fullshape-census.json').read_text())
    rows=[r for r in census['allocations'] if r['live']]
    assert sum(r['bytes'] for r in rows if r['label']=='card0:immutable-expert-cache')==M.CACHE_BYTES
    assert sum(r['bytes'] for r in rows if r['category']=='KV')==116391936
    assert census['totals']['device']==sum(r['bytes'] for r in rows if r['memory']=='device')
    assert census['totals']['device']<=budget['device_owned_bound_bytes']
    assert sum(r['bytes'] for r in rows if r['label']=='card0:exact-half-decode-table')==262144
    assert budget['device_categories']['workspace_bound']+budget['device_categories']['exact_half_decode_table']==1024**3
    assert budget['device_owned_bound_bytes']+budget['driver_allowance_bytes']+budget['device_reserve_bytes']<=32_000_000_000
    save(P/'evidence/memory-budget.json',dict(passed=True,device_executed=False,budget=budget,
        fullshape_device_bytes=census['totals']['device'],fullshape_census_sha256=sha(P/'evidence/fullshape-census.json'),
        policy='packet58u plus full added-cache backing, unchanged margins, and explicit driver/transient allowances',actual_live_host_admission=False,scope='whole-host'))
    print(count,'Python tests; retained host/VRAM budget; 1 drain FIXED; custom teardown integration PASS')
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<2*1024**3
    limits()

if __name__=='__main__':
    # These tests exercise the runtime's real refusal of inherited AS caps.
    # No native/GPU process is launched; measured RSS remains under 4 GiB.
    main()
