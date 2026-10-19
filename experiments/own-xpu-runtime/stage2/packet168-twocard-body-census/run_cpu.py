"""Landlocked native lifecycle probe; no model files or GPU nodes allowed."""
import importlib.util,json,os,resource,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,limits,turn,save,sha
import native_env
def main():
    limits();ops=P.parents[1]/'ops';sys.path.append(str(ops))
    spec=importlib.util.spec_from_file_location('p168_sandbox',ops/'rehearse_entry.py')
    R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
    B=P/'build/preparation163';binary=B/'prepare-probe'
    built=json.loads((P/'evidence/cpu-builder-status.json').read_text())
    assert built.get('passed')is True and built['binary_sha256']==sha(binary) and built['fixture_sha256']==sha(P/'native_fixture.cpp'),'stale or failed CPU build'
    old=P.parent/'packet163-full-gate/two-card'
    probes=json.loads((old/'evidence/preparation-probe.json').read_text())['probes']
    metadata=[f for f in (P/'inputs').rglob('*')if f.is_file()]+[P/'selection.json',P/'dispatch.json',P/'memory-plan.json']
    metadata+=list((P/'native-source').rglob('*.bf16'))+list((P/'native-source').rglob('*manifest*.json'))
    metadata += [Path('/proc/self/status'),Path('/proc/self/fdinfo'),Path('/proc/meminfo')]
    results=[]
    for rank,probe in enumerate(probes):
        dest=B/('run-'+str(time.time_ns())+'-'+str(rank));dest.mkdir()
        argv=[str(binary),*[s.replace(str(old),str(P))for s in probe['real_native_argv'][1:]],'--census-probe']
        env=native_env.environment('B');env['ENTRY_PREPARE_OUTPUT']=str(dest)
        with turn(),(dest/'stdout.log').open('w')as out,(dest/'stderr.log').open('w')as err:
            child=subprocess.Popen(argv,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
              preexec_fn=lambda:R.prepare_restrict(binary,metadata,dest))
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
          qualification='partial native lifecycle only; transfer/split head/full arm sequence incomplete',results=results))
        if child.returncode:raise RuntimeError(row['stderr'])
        rows=[json.loads(line)for line in (dest/'packet168-probes.jsonl').read_text().splitlines()]
        sensors=[json.loads(line)for line in (dest/'host-memory.jsonl').read_text().splitlines()]
        assert len(rows)==132 and all(r['repair_exact']and r['restore_exact'] for r in rows)
        real=[r for r in sensors if r.get('phase','').startswith('packet168-')]
        assert len(real)==132*9 and all(r['MemAvailable']>0 for r in real)
        row.update(partial_lifecycle_passed=True,observations=len(rows),real_sensor_samples=len(real),snapshot_poison_restored=True)
    save(P/'evidence/native-lifecycle.json',dict(passed=False,device_executed=False,
      partial_lifecycle_passed=True,compute_is_marker_only=True,snapshot_copies_are_real=True,
      reason='full requested nine-class native sequence not implemented',results=results))
    print('PASS partial native snapshot lifecycle; full census gate remains FAIL')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
