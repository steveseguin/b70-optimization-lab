"""Replay this packet's analyzers on packet179's REAL device receipts (in-packet byte copies).

Lesson of the 2026-10-19 packaging failures: every analyzer/comparator a device row will run is
exercised here on real device output before sealing.
  1. packet179's checkpoint_check (kept unchanged) on the real row-b save/restore receipts and the
     real row-a reference reproduces packet179's own checkpoint receipt;
  2. file-stream checks and the drain proof on the real per-leg native receipts;
  3. manifest_semantics (the Python mirror of the engine's token-state cross-checks) passes on the
     real packet179 gate checkpoint and refuses tampered copies;
  4. p179_identity (row a's gate) passes on the real row-a outputs, cross-checked against the
     independent row-a summary.json, and reports the first divergence on a mutated copy;
  5. measurement.aggregate and screen.report_completed (full512, device_executed=True, with the
     p179 identity receipt) on the real row-a report-inputs reproduce packet179's summary metrics;
  6. first_divergence/compare_streams edge cases on real token values.
No device, no model reads; nothing here is a new measurement.
"""
import copy,hashlib,json,math,shutil,struct,sys,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/sys.argv[1];sys.path.insert(0,str(p))
import measurement as M,worker,screen
read=lambda f:json.loads(Path(f).read_text())
R=p/'lineage/packet179-receipts'
copies=read(R/'COPY-MANIFEST.json')['entries']
for row in copies:
    data=(p/row['copy_relative']).read_bytes()
    assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['copy_relative']
checks={}
# 1. packet179 checkpoint gate replay.
legs={leg:read(R/'row-b/run/run'/leg/'native/result.json') for leg in ('save','restore1','restore2')}
reference=read(R/'row-a/run/native/incident-retrospective/result.json')
oracle=read(p/'lineage/oracle128/incident-retrospective.json')['tokens']
replay=M.checkpoint_check(legs['save'],legs['restore1'],legs['restore2'],reference,oracle,256,128)
original=read(R/'row-b/run/checkpoint-receipt.json')
for key in ('merged_tokens','reference_tokens_compared','repeat_restore_identical','save_eos_free'):assert replay[key]==original[key],key
for key in ('cold_prefix_ms','restore_continuation_wall_ms'):assert math.isclose(replay[key],original[key],rel_tol=1e-12),key
assert replay['oracle_check']==original['oracle_check']
def refuses(fn):
    try:fn()
    except (ValueError,KeyError):return True
    raise AssertionError('invalid evidence accepted')
bad=copy.deepcopy(legs['restore2']);bad['tokens'][9]^=1
assert refuses(lambda:M.checkpoint_check(legs['save'],legs['restore1'],bad,reference,oracle,256,128))
checks['packet179_checkpoint_check_replay']=dict(passed=True,merged_tokens=replay['merged_tokens'],cold_prefix_ms=replay['cold_prefix_ms'],
    restore_continuation_wall_ms=replay['restore_continuation_wall_ms'],mutated_restore_refused=True)
# 2. Streams and drain proof on real native receipts.
streams={}
for leg in ('save','restore1','restore2'):
    streams[leg]=M.check_file_stream(R/'row-b/run/run'/leg/'native/timings.jsonl')
    M.stream_check(legs[leg])
streams['row-a incident timings']=M.check_file_stream(R/'row-a/run/native/incident-retrospective/timings.jsonl')
streams['row-a incident prefill']=M.check_file_stream(R/'row-a/run/native/incident-retrospective/prefill-timings.jsonl')
assert (R/'row-b/run/run/restore1/native/prefill-timings.jsonl').stat().st_size==0,'restore legs have an empty prefill stream'
drain=worker.prove_drain([read(R/'row-b/run/run'/leg/'native/receipt.json') for leg in ('save','restore1','restore2')])
assert drain==read(R/'row-b/run/teardown.json')
checks['streams_and_drain']=dict(passed=True,rows=streams,drain=drain)
# 3. Manifest semantics on the real gate checkpoint (packet179 v1 format) and tampered copies.
gate=R/'row-b/run/checkpoints/gate';manifest=read(gate/'manifest.json')
N=manifest['token_state']['position'];tokens=list(struct.unpack('<%di'%N,(gate/'tokens.bin').read_bytes()))
assert hashlib.sha256((gate/'tokens.bin').read_bytes()).hexdigest()==manifest['token_state']['tokens_sha256']
small={n:(gate/(n+'.bin')).read_bytes() for n in ('position','next_token','token','error','token_history')}
for n,data in small.items():
    blob=next(b for b in manifest['blobs'] if b['name']==n);assert hashlib.sha256(data).hexdigest()==blob['sha256'],n
semantics=M.manifest_semantics(manifest,tokens,small)
assert semantics['passed'] and N==342 and semantics['pending_token']==legs['save']['tokens'][-1],semantics
assert tokens==list(map(int,(p/'inputs/incident-retrospective/tokens.txt').read_text().split()))+legs['save']['tokens'][:-1]
tampered=copy.deepcopy(manifest);tampered['token_state']['token_history'][0]+=1
assert not M.manifest_semantics(tampered,tokens,small)['passed']
moved=dict(small,position=struct.pack('<i',N+1))
assert not M.manifest_semantics(manifest,tokens,moved)['passed']
pending=dict(small,next_token=struct.pack('<i',7))
assert not M.manifest_semantics(manifest,tokens,pending)['passed']
checks['manifest_semantics_real_gate']=dict(passed=True,position=N,pending_token=semantics['pending_token'],
    blobs_checked=semantics['blobs_checked'],tampered_history_refused=True,position_blob_refused=True,pending_blob_refused=True)
# 4. Row a's packet179 identity gate on real outputs.
ref=read(p/'reference-p179-row-a.json')
observed={pid:read(R/'row-a/run/native'/pid/'result.json')['tokens'] for pid in ref['prompts']}
summary=read(R/'row-a/summary.json')
by_summary={r['prompt_id']:r['tokens'] for r in summary['requests']}
by_summary['prefill512']=summary['prefill_request']['tokens']
assert by_summary==observed,'reference-p179-row-a.json disagrees with packet179 row-a summary.json'
identity=M.p179_identity(observed,ref)
assert identity['passed'] and identity['compared_prompts']==13
mutated=copy.deepcopy(observed);mutated['code-review'][300]^=1
bad_identity=M.p179_identity(mutated,ref)
row=next(r for r in bad_identity['rows'] if r['prompt_id']=='code-review')
assert not bad_identity['passed'] and row['first_divergence']['index']==300 and row['actual_tokens'] and row['expected_tokens']
short=copy.deepcopy(observed);short['customer-email']=short['customer-email'][:-1]
assert not M.p179_identity(short,ref)['passed']
assert not M.p179_identity({k:v for k,v in observed.items() if k!='prefill512'},ref)['passed']
checks['p179_identity_real_row_a']=dict(passed=True,compared_prompts=13,independent_summary_cross_check=True,
    mutation_first_divergence=300,short_stream_refused=True,missing_prompt_refused=True)
# 5. Aggregate and full512 report on real row-a report inputs.
inputs=read(R/'row-a/run/report-inputs.json')
key='class_balanced_tok_s_1_100_intervals_after_ttft'
aggregate=M.aggregate(inputs['requests'],inputs['prefill'],summary['identity'])
assert math.isclose(aggregate[key]['median'],summary[key]['median'],rel_tol=1e-12) and aggregate['strict512'] is summary['strict512'] is True
assert aggregate['quality']==summary['quality']
with tempfile.TemporaryDirectory(prefix='p181-report-real-') as td:
    out=Path(td);(out/'run').mkdir()
    shutil.copyfile(R/'row-a/run/report-inputs.json',out/'run/report-inputs.json')
    worker.save(out/'run/p179-identity.json',identity)
    result=screen.report_completed(out,dict(device_executed=True),dict(lane='A',bracket=dict(kind='full512'),measurement_identity=summary['identity']),
        dict(scope='replay of packet179 real receipts'))
    assert math.isclose(result[key]['median'],summary[key]['median'],rel_tol=1e-12) and result['strict512']
    assert result['packet179_row_a_identity']['passed'] and result['packet179_row_a_identity']['compared_prompts']==13
    worker.save(out/'run/p179-identity.json',bad_identity)
    assert refuses(lambda:screen.report_completed(out,dict(device_executed=True),dict(lane='A',bracket=dict(kind='full512'),
        measurement_identity=summary['identity']),dict(scope='replay')))
checks['aggregate_and_report_real_row_a']=dict(passed=True,class_balanced_median=aggregate[key]['median'],strict512=True,
    report_requires_passed_identity_on_device=True)
# 6. Comparator edge cases on real token values.
a=legs['save']['tokens']
assert M.first_divergence(a,a) is None and M.compare_streams('same',a,a)['passed']
assert M.first_divergence(a,a[:-1])=={'index':255,'actual':a[255],'expected':None,'actual_length':256,'expected_length':255}
b=list(a);b[0]^=1;assert M.first_divergence(b,a)['index']==0
assert M.first_divergence([],a)['index']==0 and not M.compare_streams('empty',[],a)['passed']
checks['comparator_edges']=dict(passed=True,cases=['equal','length','first token','empty'])
worker.save(p/'evidence/p179-receipt-replay.json',dict(passed=True,device_executed=False,source_is_real_device_evidence=True,
    new_measurement=False,copies_verified=len(copies),checks=checks,
    scope='packet181 (inherited packet180) analyzers and the retained packet179 analyzer replayed on packet179 real device receipts (byte copies in lineage/packet179-receipts); no device'))
print(p.name,'packet179 real-receipt replay PASS',sorted(checks))
