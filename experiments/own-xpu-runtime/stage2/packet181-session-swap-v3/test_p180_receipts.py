"""Replay packet180's analyzers, then the packet181 analyzer, on packet180's REAL device receipts.

Lesson of the 2026-10-19 packaging failures: every analyzer a device row will run is exercised on
real device output before sealing. Receipts are in-packet byte copies (lineage/packet180-receipts,
COPY-MANIFEST.json) of the 2026-10-22 window (lanequeue-A35):
  1. row b: packet180's lifecycle_check (kept byte-for-byte in this packet's measurement.py) on
     the real five-leg results, the real S1/S2 manifests + tokens.bin + control blobs, the S2b
     manifest copy (its tokens/control blobs are S2's, proven by sha equality, as the device gate
     proved S2b == S2 before deleting S2b) and the real host-tool outputs reproduces the device
     lifecycle receipt exactly: 36 gates, comparisons, timing;
  2. row b: packet181's lifecycle_check_v3 with expect=v1.2+p180 passes the same receipts; the
     missing prompt-path fields read as "incremental" (legacy); the prefill observation is
     computed from the real per-position prompt-step rows;
  3. the v3 gates are live on real data: expect=v1.2+p181 fails exactly the three manifest
     identity gates (label experimental); an append path recorded as "chunked", or a reference
     path that differs, fails the path gates;
  4. row a: packet180's aggregate and full512 report reproduce 31.78 tok/s on the real report
     inputs; the row-a identity gate (packet179 row-a reference, used unchanged by this packet's
     row a) passes on packet180's real outputs and equals packet180's own p179-identity receipt;
  5. streams and drain proofs on the real native receipts of both rows;
  6. prompt-mechanism evidence: per-position prompt-step wall_ms of the cold reference, the
     append and the warm-process prefill512 request, bucketed, recorded as data.
No device, no model reads; nothing here is a new measurement.
"""
import copy,hashlib,json,math,shutil,statistics,struct,sys,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/sys.argv[1];sys.path.insert(0,str(p))
import measurement as M,worker,screen
read=lambda f:json.loads(Path(f).read_text())
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
R=p/'lineage/packet180-receipts'
copies=read(R/'COPY-MANIFEST.json')['entries']
for row in copies:
    data=(p/row['copy_relative']).read_bytes()
    assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['copy_relative']
checks={}
L=worker.LIFECYCLE;ids=L['checkpoint_ids']
prompt=list(map(int,(p/'inputs'/L['prompt_id']/'tokens.txt').read_text().split()))
turn=M.lifecycle_turn(L,p)
oracle=read(p/'lineage/oracle128'/(L['prompt_id']+'.json'))['tokens']
p179=read(p/'reference-p179-row-a.json')['prompts'][L['prompt_id']]['tokens']
B=R/'row-b/run';receipt=read(B/'lifecycle-receipt.json');summary_b=read(R/'row-b/summary.json')
assert receipt['passed'] and len(receipt['gates'])==36 and summary_b['passed'] and summary_b['gates']==receipt['gates']
assert (B/'inputs/new.txt').read_text().split()==list(map(str,prompt+p179[:L['K']]+turn)),'device NEW == P + gen[0:K] + T'

# ---- 1. packet180's lifecycle_check reproduces the device receipt
legs=('save-s1','append-s2','resume-s2','reference','append-s2b')
results={}
for leg in legs:
    results[leg]=read(B/'run'/leg/'native/result.json');results[leg]['request_reset_sha256']=[sha(B/'run'/leg/'native/reset.json')]
assert receipt['reset_sha256']=={leg:results[leg]['request_reset_sha256'] for leg in legs},'reset receipt hashes'
manifests={}
def small_blobs(folder):return {n:(folder/(n+'.bin')).read_bytes() for n in ('position','next_token','token','error','token_history')}
for key in ('S1','S2'):
    cid=ids[key];folder=B/'checkpoints'/cid;manifest=read(folder/'manifest.json')
    tokens=list(struct.unpack('<%di'%manifest['token_state']['position'],(folder/'tokens.bin').read_bytes()))
    assert sha(folder/'tokens.bin')==manifest['token_state']['tokens_sha256']
    small=small_blobs(folder)
    for n,data in small.items():assert hashlib.sha256(data).hexdigest()==next(b['sha256'] for b in manifest['blobs'] if b['name']==n),(cid,n)
    manifests[cid]=dict(manifest=manifest,sha256=sha(folder/'manifest.json'),fields_sha256=sha(folder/'fields.tsv'),
        semantics=M.manifest_semantics(manifest,tokens,small))
s2=B/'checkpoints'/ids['S2'];copy2b=B/'s2b-manifest-copy';m2b=read(copy2b/'manifest.json')
assert m2b['token_state']['tokens_sha256']==sha(s2/'tokens.bin'),'S2b token history == S2 token history (sha)'
small=small_blobs(s2)
for n,data in small.items():assert hashlib.sha256(data).hexdigest()==next(b['sha256'] for b in m2b['blobs'] if b['name']==n),('S2b control blob == S2',n)
tokens=list(struct.unpack('<%di'%m2b['token_state']['position'],(s2/'tokens.bin').read_bytes()))
manifests[ids['S2b']]=dict(manifest=m2b,sha256=sha(copy2b/'manifest.json'),fields_sha256=sha(copy2b/'fields.tsv'),semantics=M.manifest_semantics(m2b,tokens,small))
for cid,m in manifests.items():
    rm=receipt['manifests'][cid]
    assert m['sha256']==rm['sha256'] and m['fields_sha256']==rm['fields_sha256'] and m['semantics']==rm['semantics'],cid
tools={}
for key,row in receipt['tools'].items():
    flag,target=row['argv'][1],row['argv'][2];stem=flag.lstrip('-')+'-'+Path(target).name
    out=(B/'tools'/(stem+'.stdout.json')).read_text();err=(B/'tools'/(stem+'.stderr.jsonl')).read_text()
    rebuilt=dict(argv=row['argv'],returncode=row['returncode'],stdout_object=json.loads(out),stdout_lines=len(out.splitlines()),stderr_json_lines=True)
    for line in err.splitlines():
        try:json.loads(line)
        except ValueError:rebuilt['stderr_json_lines']=False
    assert rebuilt['stdout_lines']==row['stdout_lines'] and rebuilt['stderr_json_lines']==row['stderr_json_lines'] and rebuilt['stdout_object'].get('ok')==row['ok'],key
    for k in ('directory_removed','lock_removed'):
        if k in row:rebuilt[k]=row[k]
    tools[key]=rebuilt
base=M.lifecycle_check(results,manifests,tools,L,prompt,turn,p179,oracle)
assert base['passed'] and not base['problems'] and len(base['gates'])==36
for key in ('gates','comparisons','timing','oracle_check','reference_tokens','reference_natural_stop'):
    assert base[key]==receipt[key],('packet180 lifecycle_check does not reproduce the device receipt',key)
checks['packet180_lifecycle_check_reproduces_device_receipt']=dict(passed=True,gates=len(base['gates']),all_gates_passed=True,
    comparisons_identical=True,timing_identical=True,append_prefill_ms=base['timing']['append_prefill_ms'],
    cold_vs_restore_ratio=base['timing']['cold_vs_restore']['ratio'],
    s2b_inputs='S2b manifest copy + S2 tokens.bin/control blobs (sha-equal to S2b manifest entries)')

# ---- 2. packet181's lifecycle_check_v3 on the same receipts (expect v1.2+p180, legacy fields)
prefill={leg:M.prefill_rows(B/'run'/leg/'native/prefill-timings.jsonl') for leg in legs}
assert len(prefill['reference'])==468 and len(prefill['append-s2'])==126 and prefill['append-s2'][0][0]==342 and prefill['resume-s2']==[]
v3=M.lifecycle_check_v3(results,manifests,tools,L,prompt,turn,p179,oracle,prefill,expect='v1.2+p180')
assert v3['passed'] and not v3['problems'] and len(v3['gates'])==38,v3['problems']
assert v3['base_passed'] and v3['replaced_base_gates']==['manifest identity s1','manifest identity s2','manifest identity s2b']
assert all(v3['gates'][k]==base['gates'][k] for k in base['gates'] if not k.startswith('manifest identity ')),'non-replaced base gates unchanged'
assert v3['record_gates'].startswith('not evaluated')
assert {k:v['path'] for k,v in v3['prefill_paths'].items()}=={'reference':'incremental','append-s2':'incremental','append-s2b':'incremental'}
assert all(v['source'].startswith('legacy') for v in v3['prefill_paths'].values()),'packet180 receipts carry no path field'
obs=v3['prefill_observation'];a2=obs['append']['append-s2'];a2b=obs['append']['append-s2b']
assert obs['gated'] is False and a2['tokens']==127 and a2['tokens_source'].startswith('derived')
assert math.isclose(obs['cold']['ms_per_token'],16014.508663/469,rel_tol=1e-12) and math.isclose(a2['ms_per_token'],5594.092459/127,rel_tol=1e-12)
assert 1.25<a2['ratio_to_cold_per_token']<1.35 and a2['within_bound'] is False and a2b['within_bound'] is False
assert 0.95<a2['matched_warmth']['ratio']<1.0 and 1.4<a2['same_positions']['ratio']<1.5
checks['packet181_v3_on_packet180_receipts']=dict(passed=True,expect='v1.2+p180',gates=len(v3['gates']),
    prefill_paths=v3['prefill_paths'],observation=dict(cold_ms_per_token=obs['cold']['ms_per_token'],
        append=dict((leg,dict(ms_per_token=o['ms_per_token'],ratio_to_cold_per_token=o['ratio_to_cold_per_token'],within_bound=o['within_bound'],
            matched_warmth_ratio=o['matched_warmth']['ratio'],matched_warmth_append_ms=o['matched_warmth']['append_ms'],
            matched_warmth_reference_ms=o['matched_warmth']['reference_first_steps_ms'],same_positions_ratio=o['same_positions']['ratio'],
            same_positions_reference_ms=o['same_positions']['reference_ms'])) for leg,o in obs['append'].items())))

# ---- 3. the v3 gates are live on real data
strict=M.lifecycle_check_v3(results,manifests,tools,L,prompt,turn,p179,oracle,prefill,expect='v1.2+p181')
assert not strict['passed'] and sorted(strict['problems'])==['append prefill record append-s2','append prefill record append-s2b',
    'manifest identity s1','manifest identity s2','manifest identity s2b','reference prefill record','resume prefill record','save prefill record'],strict['problems']
chunked=copy.deepcopy(results);chunked['append-s2']['checkpoint']['restore']['append_prefill_path']='chunked'
r=M.lifecycle_check_v3(chunked,manifests,tools,L,prompt,turn,p179,oracle,prefill,expect='v1.2+p180')
assert r['problems']==['append prefill path append-s2'],r['problems']
diff=copy.deepcopy(results);diff['reference']['checkpoint']['prefill']=dict(path='chunked',first_position=0,tokens=469,ms=diff['reference']['prefill_ms'])
r=M.lifecycle_check_v3(diff,manifests,tools,L,prompt,turn,p179,oracle,prefill,expect='v1.2+p180')
assert sorted(r['problems'])==['append prefill path append-s2','append prefill path append-s2b'],r['problems']
flip=copy.deepcopy(results);flip['append-s2b']['tokens'][64]^=1
r=M.lifecycle_check_v3(flip,manifests,tools,L,prompt,turn,p179,oracle,prefill,expect='v1.2+p180')
assert 'append repeat identical' in r['problems'] and r['gates']['append repeat identical']['detail']['index']==64
checks['v3_gates_live_on_real_data']=dict(passed=True,
    expect_p181_on_p180_receipts='fails the 3 manifest identity gates (label experimental, contract v1.2+p180, no qualified_by) and the 5 record gates (fields absent)',
    append_path_chunked='fails append prefill path append-s2',reference_path_differs='fails both append path gates',
    repeat_divergence='fails append repeat identical at index 64')

# ---- 4. row a: packet180's aggregate/report reproduce 31.78 tok/s; identity gate on real outputs
A=R/'row-a';summary=read(A/'summary.json');key='class_balanced_tok_s_1_100_intervals_after_ttft'
inputs=read(A/'run/report-inputs.json')
aggregate=M.aggregate(inputs['requests'],inputs['prefill'],summary['identity'])
assert math.isclose(aggregate[key]['median'],summary[key]['median'],rel_tol=1e-12) and round(summary[key]['median'],2)==31.78
assert aggregate['strict512'] is summary['strict512'] is True and aggregate['quality']==summary['quality']
ref=read(p/'reference-p179-row-a.json')
observed={pid:read(A/'run/native'/pid/'result.json')['tokens'] for pid in ref['prompts']}
by_summary={r['prompt_id']:r['tokens'] for r in summary['requests']};by_summary['prefill512']=summary['prefill_request']['tokens']
assert by_summary==observed,'packet180 row-a result.json copies disagree with its summary.json'
identity=M.p179_identity(observed,ref)
assert identity['passed'] and identity['compared_prompts']==13 and identity==read(A/'run/p179-identity.json'),'identity gate does not reproduce packet180 row a'
with tempfile.TemporaryDirectory(prefix='p181-report-p180-') as td:
    out=Path(td);(out/'run').mkdir()
    shutil.copyfile(A/'run/report-inputs.json',out/'run/report-inputs.json');shutil.copyfile(A/'run/p179-identity.json',out/'run/p179-identity.json')
    result=screen.report_completed(out,dict(device_executed=True),dict(lane='A',bracket=dict(kind='full512'),measurement_identity=summary['identity']),
        dict(scope='replay of packet180 real receipts'))
    assert math.isclose(result[key]['median'],summary[key]['median'],rel_tol=1e-12) and result['strict512']
    assert result['packet179_row_a_identity']==summary['packet179_row_a_identity']
checks['row_a_real']=dict(passed=True,class_balanced_median=aggregate[key]['median'],strict512=True,
    packet180_outputs_equal_packet179_reference=True,compared_prompts=13,report_reproduced=True,
    note='row a of this packet compares with reference-p179-row-a.json (inherited unchanged); packet180 row a equals it on all 13 outputs, so equality with it is equality with packet180 row a')

# ---- 5. streams and drain on real native receipts
streams={}
for leg in legs:
    streams[leg+' timings']=M.check_file_stream(B/'run'/leg/'native/timings.jsonl')
    M.stream_check(results[leg])
    if leg!='resume-s2':streams[leg+' prefill']=M.check_file_stream(B/'run'/leg/'native/prefill-timings.jsonl')
assert (B/'run/resume-s2/native/prefill-timings.jsonl').stat().st_size==0,'the resume leg has an empty prefill stream'
assert worker.prove_drain([read(B/'run'/leg/'native/receipt.json') for leg in legs])==read(B/'teardown.json')
assert worker.prove_drain([read(A/'run/native/receipt.json')])==read(A/'run/teardown.json')
checks['streams_and_drain']=dict(passed=True,rows=streams,row_b_owners=5,row_a_owners=1)

# ---- 6. prompt-mechanism evidence (data, not a gate)
def buckets(rows,width=64):
    return [dict(first_row=i,first_position=rows[i][0],rows=len(rows[i:i+width]),mean_ms=statistics.mean(w for _,w in rows[i:i+width]),
                 median_ms=statistics.median(w for _,w in rows[i:i+width])) for i in range(0,len(rows),width)]
warm=M.prefill_rows(A/'run/native/prefill512/prefill-timings.jsonl')
cold_first=M.prefill_rows(A/'run/native/incident-retrospective/prefill-timings.jsonl')
evidence=dict(
    reference_cold_process=dict(rows=len(prefill['reference']),sum_ms=sum(w for _,w in prefill['reference']),buckets=buckets(prefill['reference'])),
    append_s2_fresh_process=dict(rows=len(prefill['append-s2']),sum_ms=sum(w for _,w in prefill['append-s2']),buckets=buckets(prefill['append-s2'])),
    append_s2b_fresh_process=dict(rows=len(prefill['append-s2b']),sum_ms=sum(w for _,w in prefill['append-s2b']),buckets=buckets(prefill['append-s2b'])),
    row_a_prefill512_warm_process=dict(rows=len(warm),sum_ms=sum(w for _,w in warm),buckets=buckets(warm),
        note='second request of row a: the process already served incident-retrospective, so the expert cache is warm'),
    row_a_first_request=dict(rows=len(cold_first),sum_ms=sum(w for _,w in cold_first),buckets=buckets(cold_first),
        note='first request of a fresh process: the first prompt positions pay the empty expert cache (and first-use costs)'),
    reading=('fresh prompts and appended tokens are stepped by the same per-position prompt step; per-position cost depends on how warm the '
             'expert cache is: ~52-54 ms over the first 64 positions of a fresh process (reference and append alike), ~28-34 ms once warm; '
             'the append process pays the cold positions over its whole 127-token span, the cold reference amortizes them over 469'))
checks['prompt_mechanism_evidence']=dict(passed=True,**evidence)
worker.save(p/'evidence/p180-receipt-replay.json',dict(passed=True,device_executed=False,source_is_real_device_evidence=True,
    new_measurement=False,copies_verified=len(copies),checks=checks,
    scope='packet180 analyzers (kept unchanged) and the packet181 v3 analyzer replayed on packet180 real device receipts (byte copies in lineage/packet180-receipts); no device'))
print(p.name,'packet180 real-receipt replay PASS',sorted(checks))
