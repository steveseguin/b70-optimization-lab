"""CPU-only copy-forward of packet58aj orchestration; never rebuild or launch."""
import hashlib,json,resource,shutil
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
O=Path(__file__).resolve().parent;R=O.parents[3];S=R/'experiments/own-xpu-runtime/stage2'
P=S/'packet58as-onecard-spinwait';A=S/'packet58aj-onecard-resident'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def edit(n,a,b):
 p=P/n;t=p.read_text();assert a in t,(n,a);p.write_text(t.replace(a,b))
H=P/'lineage/packet58asc-before';H.mkdir(exist_ok=True)
for n in ('seal.py','runtime-selection.json','record-threshold.snapshot','READY-FOR-DEVICE.json'):
 assert not (H/n).exists();shutil.copy2(P/n,H/n)
(P/'READY-FOR-DEVICE.json').unlink()
# Copy only missing Python chain files. Existing bracket, sources and binaries stay intact.
records=[]
for f in A.glob('*.py'):
 if (P/f.name).exists():continue
 t=f.read_text().replace('packet58aj-onecard-resident',P.name).replace('packet58-onecard-58aj-a','packet58-onecard-58as-a').replace('card0-58aj-a','card0-58as-a').replace('fault-review-58aj-a','fault-review-58as-a').replace('packet58aj','packet58as')
 (P/f.name).write_text(t);records.append(dict(name=f.name,parent_relpath=str(f.relative_to(R)),parent_digest=sha(f)))
save(O/'parent-provenance.json',dict(parents=records,native_recompiled=False))
shutil.copy2(A/'lineage/synthetic-lookup-receipt.json',P/'lineage/synthetic-lookup-receipt.json')
# A private provenance note; snapshot hashes do not masquerade as mutable parent pins.
shutil.copy2(R/'scripts/packet58_onecard_record_threshold.json',P/'record-threshold.snapshot')
s=json.loads((P/'runtime-selection.json').read_text());s['wait_policy']='spin';save(P/'runtime-selection.json',s)
edit('views.py',"dict(lookups='resident',view=", "dict(wait_policy='spin',lookups='resident',view=")
edit('composition.py',"FLAGS = {'--lookups'", "FLAGS = {'--wait-policy':'spin', '--lookups'")
edit('suite_driver.py',"'--lookups','resident'", "'--wait-policy','spin','--lookups','resident'")
# Surface the selected policy in receipts as well as the sealed argv.
edit('suite_driver.py',"summary.update(**DIMENSIONS,", "summary.update(wait_policy='spin',**DIMENSIONS,")
# Replay only the completed packet58as v5: no nonexistent smoke prerequisite.
p=P/'screen_gate.py';t=p.read_text().replace("V=P/'screen/evidence/card0-58ajb-screen-a'", "V=P/'screen/evidence/card0-58as-v5-a'")
t=t.replace("for arm in ('smoke','resident'):","for arm in ('resident',):")
t=t.replace("    D.require(summaries['smoke'].get('smoke_passed') is True,'smoke failed')\n",'')
t=t.replace('smoke_passed=True','bracket_passed=True');p.write_text(t)
# verify_ready retains the exact comparator, with no post-result threshold amendment.
p=P/'verify_ready.py';t=p.read_text();start=t.index('    # Post-result');end=t.index('\ndef command_argv',start)
t=t[:start]+"    require(result['candidate_beats_all_controls'], 'spin must beat EVERY warm poll control by 0.5%; drift <=3%')\n    return dict(result,minimum_gain=result['minimum_gain_vs_best_control'],record_gain_measured=False)\n"+t[end:]
t=t.replace("return dict(result,smoke_passed=True", "return dict(result,bracket_passed=True")
t=t.replace("selection.get('lookups')=='resident'", "selection.get('wait_policy')=='spin' and seal.get('wait_policy')=='spin' and selection.get('lookups')=='resident'")
p.write_text(t)
policy=json.loads((A/'submission-policy.json').read_text());policy['schema']='packet58as.submission-policy.v1'
policy['ledger_sha256']=sha(P/'record-threshold.snapshot');ledger=json.loads((P/'record-threshold.snapshot').read_text())
policy['supersedes']={k:ledger['records'][-1][k] for k in ('reference_submission','threshold_tok_s')}
policy['readiness_amendment']='58as v5 A0/B0/A1/B1/A2: 31.901/34.577/31.838/34.568/31.807 tok/s; A0 warm-up excluded; 60/60 exact, drift 0.096%, minimum gain +8.58%; readiness only.'
policy['wait_disclosure']='Bounded spin: host CPU policy, owner-thread CPU ~33% vs ~25% poll (one core); 250 us spin then <=20 us sleeps; no setting or governor change; arithmetic unchanged.'
policy['diagnostic_disclosure']='58aq diagnostic: publication/drain 1.108 ms/token plus other 1 ms poll waits; diagnostic only.'
policy['scope'].update(rule='packet58as.onecard-128-preparation.2026-10-19',authority='Owner packet58asc brief; preparation only; coordinator submits.')
policy['public_record_check']['disclosure']='Pinned local ledger only; public check stale, no global-record claim.'
save(P/'submission-policy.json',policy)
p=P/'packet58_submission.py';t=p.read_text();start=t.index('RERUN_DISCLOSURE =');end=t.index('\n\ndef require',start)
t=t[:start]+"RERUN_DISCLOSURE = 'Fresh packet58as chain a; no selection between attempts.'\n"+t[end:]
t=t.replace("+result['public_record_check']['disclosure']+' '+POLICY['readiness_amendment']+' '+RERUN_DISCLOSURE", "+result['public_record_check']['disclosure']+' '+POLICY['readiness_amendment']+' '+POLICY['wait_disclosure']+' '+POLICY['diagnostic_disclosure']+' '+RERUN_DISCLOSURE")
t=t.replace("'second", "'second")
p.write_text(t)
# Synthetic test argv must include the new fixed dimension.
edit('test_submission.py',"'--lookups','resident'", "'--wait-policy','spin','--lookups','resident'")
(P/'WINDOW.md').write_text('''# Packet58as record-chain coordinator contract

CPU preparation only. Recheck seal.py --verify and verify_ready.py --output ready.json.
Use the exact chain_command in ready.json. Unit: packet58-onecard-58as-a.
Fresh output: evidence/card0-58as-a. Fresh fault review:
evidence/fault-review-58as-a.json (fault_review.py immediately before launch).

Pause and drain both lanes. Hold the whole host through
K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second gaps.
Freeze Codex from WS through WS128 completion; no compiles or model/full-shape
reads during timing. One attempt, no retry, graceful teardown on every exit.
K1a/K1b/KD use helper cores and nice19; W windows use lane-A cores and nice0,
as in packet58aj. No service restoration or host setting change.

Use the existing packet58as bracket binary, never rebuild. Every model window
uses --wait-policy spin, --wait-seconds 300, resident lookups, BF16 KV at 4096,
21,552,729,600 cache bytes, max cache, overlap maintenance, zero-copy misses,
tile16, p60fusion, HC-wide, wide64+halfcache, other fusion and ordered retirement.
K1 proves exact fixture bytes and zero-copy; all model windows must exactly
match iq3-p49-split32-v1. Preserve memory, fault, drain and storage admission.

The completed v5 bracket is readiness evidence only: 60/60 exact; A0 warm-up
excluded; both spin views beat every warm poll control, minimum +8.58%, drift
0.096%. Owner-thread CPU about 33% spin vs 25% poll, measured as one core.
Bounded spin is a host CPU wait policy (250 us then <=20 us sleeps), not a
setting/governor or arithmetic change. See the packet58aq diagnostic note.

Only fresh WS128 supplies record timing. It must exceed the pinned one-card
31.966819787781944 tok/s (31.966820 displayed), cmveqsmsl00ebrf014yvrsosx,
and the live ledger. Scope is 128 tokens, strict512 false; a second fresh timing
remains pending. Submission preparation is offline; this handoff publishes no
performance claim and performs no network submission.
''')
print('Copied chain harness; existing binary and completed screen untouched')
