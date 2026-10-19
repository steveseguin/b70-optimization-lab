"""Sandboxed CPU-only proof of the existing binary's record-chain interface."""
import hashlib,json,resource,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait'
sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'))
import entry_sandbox,launch_env
entry_sandbox.MEMORY=2_000_000_000
resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
binary=P/'build/device/own-rt-iq3'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
checks=[]
for args in (['--help'],['--wait-policy','spin'],['--hc','spin']):
 cp=entry_sandbox.run(launch_env.env_command([str(binary),*args]),binary=binary)
 checks.append(dict(argv=args,returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr))
assert checks[0]['returncode']==0 and '--wait-policy' not in checks[0]['stdout']
assert checks[1]['returncode']!=0 and 'unknown option' in (checks[1]['stdout']+checks[1]['stderr']).lower()
assert checks[2]['returncode']!=0 and 'HC dimension' in checks[2]['stdout']+checks[2]['stderr']
old=json.loads((P/'lineage/packet58asc-before/screen-build-receipt.json').read_text())
assert sha(binary)==old['artifacts']['build/device/own-rt-iq3']
reason=('Existing bracket binary has no --wait-policy option; --hc spin also refuses. '
        'Single-view bracket_table uses a.hc (production/p60fusion), so spin_enabled is false. '
        'Spin is selectable only through --bracket-inputs, which permits S0 at 64 tokens or '
        'A0/B0/A1/B1/A2 at 128 tokens, requires 12 prompts and retain-steps none; '
        'it cannot express KD/W2m (8 tokens) or WS (retained layers). '
        'No compliant seven-window spin chain is possible without changing the native binary.')
row=dict(schema='packet58asc.chain-native-interface.v1',passed=False,diagnostic_passed=True,device_executed=False,native_recompiled=False,binary_sha256=sha(binary),matches_completed_bracket=True,reason=reason,checks=checks,source_evidence=[dict(name=n,parent_relpath=str((P/n).relative_to(ROOT)),parent_digest=sha(P/n)) for n in ('native/generated/main.cpp','native/bracket_table.hpp','native/spin_wait.hpp')],peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
(P/'evidence/chain-native-interface.json').write_text(json.dumps(row,indent=2)+'\n')
print(reason)
print('PASS bounded parser diagnosis; chain ABI FAIL; no GPU/model access')
