"""packet58asd: sandboxed CPU-only proof of the rebuilt chain binary's interface.

The p58asc version proved the bracket binary could not select spin for the
record windows (kept in lineage/packet58asd-before via git history). This
version proves the rebuilt device binary lists --wait-policy, refuses an
unknown policy value before any device or model access, and that the bracket
device binary still refuses the flag. Host-build acceptance in every chain
model window is proven by the packet's evidence/wait-policy.json.
"""
import hashlib,json,resource,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait'
sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'))
import entry_sandbox,launch_env
entry_sandbox.MEMORY=2_000_000_000
resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
binary=P/'build/device/own-rt-iq3';bracket=P/'build/bracket/device/own-rt-iq3'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
build=json.loads((P/'evidence/build.json').read_text())
assert sha(binary)==build['artifacts']['build/device/own-rt-iq3']
old={r['name']:r['parent_digest'] for r in build['bracket_native']}
assert sha(bracket)==old['build/device/own-rt-iq3']
screen=json.loads((P/'lineage/packet58asc-before/screen-build-receipt.json').read_text())
assert screen['artifacts']['build/device/own-rt-iq3']==old['build/device/own-rt-iq3']!=sha(binary)
checks=[]
for target,args in ((binary,['--help']),(binary,['--wait-policy','bogus']),(bracket,['--help']),(bracket,['--wait-policy','spin'])):
 cp=entry_sandbox.run(launch_env.env_command([str(target),*args]),binary=target)
 checks.append(dict(binary='chain' if target==binary else 'bracket',argv=args,returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr))
assert checks[0]['returncode']==0 and '--wait-policy' in checks[0]['stdout'].split() and '(default:poll)' in checks[0]['stdout']
assert checks[1]['returncode']!=0 and 'wait policy dimension' in checks[1]['stdout']+checks[1]['stderr']
assert checks[2]['returncode']==0 and '--wait-policy' not in checks[2]['stdout']
assert checks[3]['returncode']!=0 and 'unknown option --wait-policy' in checks[3]['stdout']+checks[3]['stderr']
# Apart from the new option the help text is unchanged.
assert checks[0]['stdout'].replace('--wait-policy poll|spin (default:poll) ','')==checks[2]['stdout']
gate=json.loads((P/'evidence/wait-policy.json').read_text())
assert gate['passed'] and not gate['device_executed'] and [r['window'] for r in gate['records']['parser']]==['KD','W2m','WS','WS128x','WS128']
assert all(r['parsed_wait_policy']=={'spin':'spin','default':'poll','intel-spin':'spin'} for r in gate['records']['parser'])
patch=P/'chain-interface.patch'
row=dict(schema='packet58asd.chain-native-interface.v1',passed=True,diagnostic_passed=True,device_executed=False,native_recompiled=True,
 binary_sha256=sha(binary),bracket_binary_sha256=sha(bracket),matches_completed_bracket=False,
 reason='Chain binary is a rebuild of the packet58as bracket binary that differs only by the process-wide --wait-policy poll|spin CLI option (default poll). '
  'Every chain model window (KD/W2m/WS/WS128x/WS128) passes --wait-policy spin through the same p58as::wait() the bracket B views used; '
  'K1a/K1b keep the unchanged inherited K1 fixture.',
 chain_windows_accepting_spin=['KD','W2m','WS','WS128x','WS128'],default_wait_policy='poll',
 source_patch=dict(name=patch.name,parent_relpath=str(patch.relative_to(ROOT)),parent_digest=sha(patch)),
 wait_policy_gate=dict(name='wait-policy.json',parent_relpath=str((P/'evidence/wait-policy.json').relative_to(ROOT)),parent_digest=sha(P/'evidence/wait-policy.json')),
 checks=checks,
 source_evidence=[dict(name=n,parent_relpath=str((P/n).relative_to(ROOT)),parent_digest=sha(P/n)) for n in ('native/generated/main.cpp','native/bracket_table.hpp','native/spin_wait.hpp','native/generated/single_device.cpp')],
 peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
(P/'evidence/chain-native-interface.json').write_text(json.dumps(row,indent=2)+'\n')
print('PASS chain binary lists/validates --wait-policy; bracket binary refuses it; no GPU/model access')
