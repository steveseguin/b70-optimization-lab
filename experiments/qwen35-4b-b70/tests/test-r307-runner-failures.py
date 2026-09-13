#!/usr/bin/env python3
"""GPU-free failure-injection checks for the R307 campaign wrappers and engine."""
import pathlib, tempfile, subprocess, os
repo=pathlib.Path(__file__).resolve().parents[3]
engine=(repo/'experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh').read_text()
def run(script, env=None):
 return subprocess.run(['bash','-c',script],env=env,text=True,capture_output=True)
with tempfile.TemporaryDirectory() as d:
 t=pathlib.Path(d); b=t/'bin'; b.mkdir(); out=t/'out'; out.mkdir()
 for name,body in {'docker':'[[ "$1" == image ]] && echo sha256:test; exit 0','sleep':'exit 0'}.items():
  f=b/name;f.write_text('#!/bin/bash\n'+body+'\n');f.chmod(0o755)
 env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH'])
 stub=t/'engine.sh';stub.write_text('echo "$LANE" >>"'+str(t/'calls')+'"\nexit 2\n')
 strict=(repo/'experiments/qwen35-4b-b70/scripts/run-20260912-rebase-v0290-strict-chain.sh').read_text().replace('out=/mnt/fast-ai/bench-results',f'out={out}').replace('bash "${engine}"',f'bash "{stub}"')
 r=run(strict,env); assert r.returncode==2,r;assert (t/'calls').read_text().splitlines()==['qwen35-4b-w4a16'];assert not list(out.glob('*DONE'))
 print('PASS strict child exit 2 aborts before next lane; no DONE')
 # An existing failed root must not silently become success.
 used=out/'qwen35-4b-w4a16-20260912-rb1';used.mkdir();(used/'campaign-start.txt').touch()
 r=run(strict,env);assert r.returncode==2;assert not list(out.glob('*DONE'))
 print('PASS reused root fails closed')
 regression=(repo/'experiments/qwen35-4b-b70/scripts/run-20260913-r307-regression-chain.sh').read_text().replace('out=/mnt/fast-ai/bench-results',f'out={out}').replace('bash ${repo}/experiments/qwen35-4b-b70/scripts/run-20260912-rebase-v0290-strict-chain.sh',f'bash "{stub}"')
 dep=out/'rebase-v0290-20260912/boundary-conc';dep.mkdir(parents=True);(dep/'DONE').touch()
 r=run(regression,env);assert r.returncode==2,r;assert not list(out.rglob('r307-regression-DONE'))
 print('PASS regression propagates strict failure; no DONE')
 # Exercise production classifier and cleanup function bodies directly.
 classifier=engine[engine.index('fault_lines()'):engine.index('cleanup()')]
 fault_re=next(l for l in engine.splitlines() if l.startswith('fault_re='))
 for line,want in [('xe 0000:03:00.0: [drm] Xe device coredump has been deleted.',False),('xe 0000:03:00.0: [drm] GPU coredump captured',True),('xe 0000:03:00.0: [drm] Fault response',True),('watchdog: BUG: soft lockup',True)]:
  f=t/'journal';f.write_text(line+'\n');r=run(fault_re+'\n'+classifier+f'\nfault_lines "{f}"');assert bool(r.stdout.strip())==want,(line,r)
 print('PASS journal classifier ignores only old dump deletion, detects fresh faults')
 cleanup=engine[engine.index('cleanup()'):engine.index('journal_check()')]
 root=t/'campaign';root.mkdir();(root/'campaign-end.txt').touch()
 r=run(f'root={root}\nserver_pid=42\nserver_name=test\ndocker() {{ echo "$*" >>{t}/cleanup; }}\n'+cleanup+'\nexit 2')
 assert r.returncode==2;assert (root/'ABORTED').exists();assert not (root/'campaign-end.txt').exists();assert 'rm -f test' in (t/'cleanup').read_text()
 print('PASS EXIT cleanup removes owned container, preserves exit2 and invalidates success')
 # Real gate body, mock launch/workload operations, fail each comparison in turn.
 tail=engine[engine.index('if [[ " ${STAGES} " == *" strict "* ]]; then'):]
 for fail_at in range(1,5):
  n=t/'n';n.write_text('0')
  pre=f'''set -Eeuo pipefail
root={root}
STAGES=strict
DEPTH=3
launch() {{ server_name=test; server_pid=42; server_dir={root}; }}
strict_attempt() {{ :; }}
stop_server() {{ :; }}
postflight() {{ :; }}
log() {{ :; }}
abort() {{ exit 2; }}
compare_pair() {{ n=$(cat {n}); n=$((n+1)); echo "$n" >{n}; if ((n == {fail_at})); then echo 11/12; else echo 12/12; fi; }}
'''
  (root/'campaign-end.txt').unlink(missing_ok=True)
  r=run(pre+tail);assert r.returncode==2,(fail_at,r);assert not (root/'campaign-end.txt').exists()
 print('PASS G1, G2, G3a and G3b mismatches each abort before campaign-end')

 # Real ladder helper must propagate a workload failure instead of logging success.
 ladder_fn=next(l for l in engine.splitlines() if l.startswith('run_ladder()'))
 r=run('set -Eeuo pipefail\npython3() { return 7; }\nabort() { exit 2; }\nlog() { :; }\nladder=test; port=1; served_model=test; ladder_suite=test; server_dir='+str(root)+'; DEPTH=3\n'+ladder_fn+'\nrun_ladder test')
 assert r.returncode==2,r
 print('PASS ladder workload failure aborts')
 # The startup health helper checks the journal before accepting endpoint health.
 health_fn=next(l for l in engine.splitlines() if l.startswith('wait_health()'))
 r=run('set -Eeuo pipefail\nhealth_timeout=30; port=1\njournal_check() { return 1; }\nabort() { exit 2; }\ncurl() { return 0; }\n'+health_fn+'\nwait_health 42')
 assert r.returncode==2,r
 print('PASS startup fault aborts even when endpoint would be healthy')
 # Real depth stage must stop before the speculative arm after a failed benchmark.
 bench=t/'bench-w8a16-real-content-depth.sh';bench.write_text('#!/bin/bash\nexit 7\n');bench.chmod(0o755)
 r=run(f'''set -Eeuo pipefail
root={root}; repro={t}; STAGES=depth32k; DEPTH=3; port=1; served_model=test
launch() {{ server_dir={root}; server_name=test; server_pid=42; }}
log() {{ :; }}
abort() {{ exit 2; }}
stop_server() {{ :; }}
postflight() {{ :; }}
'''+tail)
 assert r.returncode==2,r
 print('PASS depth workload failure aborts')
