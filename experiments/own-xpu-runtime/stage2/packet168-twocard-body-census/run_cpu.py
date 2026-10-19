"""Landlocked native lifecycle probe; no model files or GPU nodes allowed."""
import importlib.util,json,os,resource,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,limits,turn,save,sha
from census_contract import NATIVE_ORDER,IDS,TOKENS
import native_env
def main():
    limits();ops=P.parents[1]/'ops';sys.path.append(str(ops))
    spec=importlib.util.spec_from_file_location('p168_sandbox',ops/'rehearse_entry.py')
    R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
    B=P/'build/preparation163';binary=B/'prepare-probe'
    built=json.loads((P/'evidence/cpu-builder-status.json').read_text())
    assert built.get('passed')is True and built['binary_sha256']==sha(binary) and built['fixture_sha256']==sha(P/'native_fixture.cpp'),'stale or failed CPU build'
    assert all(sha(P/name)==digest for name,digest in built['inputs_sha256'].items()),'changed native fixture dependencies'
    old=P.parent/'packet163-full-gate/two-card'
    probes=json.loads((old/'evidence/preparation-probe.json').read_text())['probes']
    metadata=[f for f in (P/'inputs').rglob('*')if f.is_file()]+[P/'selection.json',P/'dispatch.json',P/'memory-plan.json']
    metadata+=list((P/'native-source').rglob('*.bf16'))+list((P/'native-source').rglob('*manifest*.json'))
    metadata += [Path('/proc/self/status'),Path('/proc/self/fdinfo'),Path('/proc/meminfo')]
    results=[]
    # Real probe position = prompt tokens + 63 (device-census-B-v2 timings:
    # benchmark-analysis 65 tokens, last half step 127, probe 128).
    positions=[len((P/'inputs'/pid/'tokens.txt').read_text().split())+TOKENS-1 for pid in IDS]
    uncovered=len(NATIVE_ORDER)*sum(p%32==0 for p in positions)
    assert uncovered==len(NATIVE_ORDER),('expected exactly one uncovered prompt',positions)
    for rank,probe in enumerate(probes):
        dest=B/('run-'+str(time.time_ns())+'-'+str(rank));dest.mkdir()
        argv=['/usr/bin/ionice','-c3',str(binary),*[s.replace(str(old),str(P))for s in probe['real_native_argv'][1:]],'--census-probe']
        env=native_env.environment('B');env['ENTRY_PREPARE_OUTPUT']=str(dest);env['P168_PROBE_POSITIONS']=','.join(map(str,positions))
        with turn(),(dest/'stdout.log').open('w')as out,(dest/'stderr.log').open('w')as err:
            child=subprocess.Popen(argv,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
              preexec_fn=lambda:R.prepare_restrict(binary,metadata+[Path('/usr/bin/ionice')],dest))
            peak=0
            while child.poll()is None:
                try:
                    status=Path(f'/proc/{child.pid}/status').read_text()
                    rss=next(int(x.split()[1])*1024 for x in status.splitlines()if x.startswith('VmRSS:'))
                    peak=max(peak,rss)
                    if rss>4*1024**3:child.terminate();child.wait();raise ValueError('CPU RSS exceeds4GB')
                except (FileNotFoundError,StopIteration):pass
                time.sleep(.05)
        row=dict(rank=rank,returncode=child.returncode,peak_rss_bytes=peak,
          stdout=(dest/'stdout.log').read_text(),stderr=(dest/'stderr.log').read_text(),argv=argv)
        results.append(row)
        save(P/'evidence/native-lifecycle.json',dict(passed=False,device_executed=False,
          qualification='five-class isolated body lifecycle (in progress)',results=results))
        if child.returncode:raise RuntimeError(row['stderr'])
        rows=[json.loads(line)for line in (dest/'packet168-probes.jsonl').read_text().splitlines()]
        sensors=[json.loads(line)for line in (dest/'host-memory.jsonl').read_text().splitlines()]
        assert len(rows)==len(NATIVE_ORDER)*12*3 and all(r['repair_exact']and r['restore_exact'] for r in rows)
        assert f'observations={len(rows)} v2_uncovered_probe_positions={uncovered} ' in row['stdout'],row['stdout']
        assert [(r['arm'],r['prompt_index'],r['repeat']) for r in rows]==[(arm,i,k) for arm in NATIVE_ORDER for i in range(12) for k in range(3)]
        real=[r for r in sensors if r.get('phase','').startswith('packet168-')]
        assert len(real)==len(NATIVE_ORDER)*12*(6*3+3) and all(r['MemAvailable']>0 for r in real)
        row.update(output=str(dest),probe_positions=positions,v2_uncovered_probe_positions=uncovered,census_device_bytes=json.loads((dest/'census.json').read_text())['totals']['device'],partial_lifecycle_passed=True,observations=len(rows),real_sensor_samples=len(real),snapshot_poison_restored=True)
    save(P/'evidence/native-lifecycle.json',dict(passed=False,device_executed=False,
      partial_lifecycle_passed=True,compute_is_marker_only=True,snapshot_copies_are_real=True,
      final_arm_sequence_passed=True,native_order=list(NATIVE_ORDER),probe_positions=positions,
      probe_position_admitted=True,v2_uncovered_probe_positions_per_rank=uncovered,
      reason='five-class body lifecycle passes on the registered order x12 prompts x3 repeats at the real probe positions; the v2 uncovered extent (benchmark-analysis P=128) is reproduced and admitted; marker compute, real snapshot copies',results=results))
    print('PASS five-class native snapshot lifecycle (registered order, real probe positions, both ranks)')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
