"""Seal the integrated packet from current CPU receipts; never runs device code."""
import base64,hashlib,json,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def canonical(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def archived_run(root):
 root=Path(root).resolve();assert B.resolve() in root.parents,'archive root outside packet build'
 stem=P/'evidence'/('scratch-'+'-'.join(root.relative_to(B.resolve()).parts))
 archive=Path(str(stem)+'.jsonl.gz')
 if not archive.exists():archive=Path(str(stem)+'.json.gz')
 prefix=str(root.relative_to(P))+'/'
 with gzip.open(archive,'rt') as f:
  first=f.readline();header=json.loads(first)
  if isinstance(header,list):rows=header
  else:
   assert header['schema']=='packet38.scratch-stream.v1';rows=[];current=None
   for line in f:
    item=json.loads(line)
    if item['kind']=='file':
     assert current is None;current=item;digest=hashlib.sha256();size=0
     keep=item['retained'] and (item['path'].endswith(('.json','.py')) or item['path'].endswith('/state-evidence.json.gz'))
     data=bytearray() if keep else None
    elif item['kind']=='chunk':
     assert current is not None and current['retained'];chunk=base64.b64decode(item['base64'],validate=True)
     digest.update(chunk);size+=len(chunk)
     if data is not None:data.extend(chunk)
    else:
     assert item['kind']=='end' and current is not None and item['path']==current['path']
     if current['retained']:assert size==current['bytes'] and digest.hexdigest()==current['sha256'],'archived bytes differ'
     if data is not None:
      if current['path'].endswith('.gz'):current['data']=bytes(data)
      else:current['text']=data.decode()
     rows.append(current);current=None
   assert current is None,'truncated streaming archive'
 assert rows and all(r['path'].startswith(prefix) for r in rows),'archive path binding'
 table={r['path'][len(prefix):]:r for r in rows};assert len(table)==len(rows),'duplicate archived path'
 for row in rows:
  if 'text' in row:
   raw=row['text'].encode();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'archived metadata differs'
 return archive,table

def native_signature(table):
 result=json.loads(table['receipt.json']['text'])
 fixtures={name:row['sha256'] for name,row in table.items() if name.startswith(('rank0/step','rank1/step')) and name.endswith('.bf16')}
 states={str(rank):json.loads(table[f'rank{rank}/state-2147483647/state.json']['text']) for rank in (0,1)}
 final={name:row['sha256'] for name,row in table.items() if name.startswith(('rank0/state-2147483647/','rank1/state-2147483647/')) and not name.endswith('/state.json')}
 draft={name:row['sha256'] for name,row in table.items() if name.startswith(('rank0/draft-final-state/','rank1/draft-final-state/'))}
 for rank,state in states.items():
  for name,digest in state['buffers'].items():
   leaf=('alternate-'+name[len('alternate:'):] if name.startswith('alternate:') else name)+'.bin'
   assert final[f'rank{rank}/state-2147483647/{leaf}']==digest,'archived state hash differs'
 return result,dict(tokens=result['tokens'],guess_sequence=result['guess_sequence'],
  hit_miss_sequence=[{k:r[k] for k in ('position','guess','actual','hit')} for r in result['guess_rows']],
  counts={k:result['stats'][k] for k in ('guesses','hits','misses','no_guess')},fixtures=fixtures,
  final_states=states,final_state_bytes=final,draft_final_state=draft)

def bind_cpu_suite(row,host_sha):
 from suite import checker_module
 from suite_export import frozen_coverage
 manifest_path=P/'suite-cpu-manifest.json';manifest=json.loads(manifest_path.read_text())
 assert row['schema']=='packet38.real-suite-cpu.v1' and row['device_executed'] is False and row['real_model_execution'] is True
 assert row['binary_sha256']==host_sha and row['manifest_sha256']==sha(manifest_path)
 assert json.loads((P/'suite-cpu-freeze.json').read_text())['sha256']==row['manifest_sha256']
 checker=checker_module();assert row['frozen_coverage']==frozen_coverage(manifest,checker)
 assert row['export_checker_sha256']==checker.source_sha256
 entries={e['prompt_id']:e for e in manifest['prompts']};repeats=row['repeats']
 assert type(repeats) is int and repeats>0 and row['admitted_prompts']==len(entries) and row['expected_frozen_prompts']==12
 assert row['complete_frozen_suite'] is (manifest.get('complete') is True)
 requests=row['rows'];assert row['requests']==len(requests)==len(entries)*repeats
 assert {(r['prompt_id'],r['repeat']) for r in requests}=={(p,n) for p in entries for n in range(1,repeats+1)}
 root=P/row['evidence_directory'];archive,table=archived_run(root)
 assert row['scratch_archive']['path']==str(archive.relative_to(P)) and row['scratch_archive']['sha256']==sha(archive)
 assert table['suite-manifest.snapshot.json']['sha256']==row['manifest_sha256']
 snapshot=str((P/row['export_checker_snapshot']).relative_to(root))
 assert table[snapshot]['sha256']==row['export_checker_sha256'] and 'text' in table[snapshot]
 assert table['summary.json']['sha256']==row['summary_sha256'] and table['input-admission.json']['sha256']==row['input_admission_sha256']
 summary=json.loads(table['summary.json']['text']);admission=json.loads(table['input-admission.json']['text'])
 assert summary['passed'] is True and summary['device_executed'] is False and summary['same_rank_processes'] is True
 assert summary['controller']=='native' and summary['draft']=='mtp' and summary['manifest_sha256']==row['manifest_sha256']
 assert admission['passed'] is True and admission['one_model_plan_identity'] is True
 assert len(row['ranks'])==2 and {r['rank'] for r in row['ranks']}=={0,1} and len({r['pid'] for r in row['ranks']})==2
 for rank in row['ranks']:
  prefix=f"ranks/rank{rank['rank']}";launch=table[prefix+'-launch.json'];closed=table[prefix+'/receipt.json']
  assert launch['sha256']==rank['launch_sha256'] and closed['sha256']==rank['teardown_sha256']
  launch=json.loads(launch['text']);closed=json.loads(closed['text'])
  assert launch['pid']==rank['pid'] and launch['device_executed'] is False and Path(launch['argv'][0])==B/'gnu-host/own-rt-iq3'
  assert closed['passed'] is True and closed['device_executed'] is False and closed['rank']==rank['rank'] and len(closed['teardown'])==1
  assert all(t['safe_to_exit'] and t['live_bytes']==t['in_flight']==0 for t in closed['teardown'])
 summary_rows={(r['prompt_id'],r['repeat']):r for r in summary['rows']};assert len(summary_rows)==len(requests)
 for request in requests:
  entry=entries[request['prompt_id']];item=summary_rows[(request['prompt_id'],request['repeat'])]
  receipt=table[item['receipt']];result=json.loads(receipt['text']);directory=str(Path(item['receipt']).parent)+'/'
  assert item['passed'] is True and request['exact'] is True and result['passed'] is True and result['device_executed'] is False
  assert receipt['sha256']==request['receipt_sha256'] and request['binary_sha256']==result['binary_sha256']==host_sha
  assert request['controller']==result['controller']=='native' and request['draft']==result['draft']=='mtp'
  count=entry['generated_tokens'];assert len(request['tokens'])==request['token_count']==item['tokens']==count
  assert request['tokens']==result['tokens'] and request['token_sha256']==canonical(result['tokens'])
  assert request['stats']==result['stats'] and request['rank_trace_sha256']==canonical(result['rank_trace'])
  oracle=result['oracle_check'];assert oracle['passed'] is True and oracle['tokens']==count and oracle['fixture_files']==min(count,8)*48
  assert request['run_checker_sha256']==oracle['checker_sha256']==admission['checker_sha256']
  assert request['export_checker_sha256']==row['export_checker_sha256']
  for rank in (0,1):
   assert any(r['rank']==rank and r['op']==1 for r in result['rank_trace'])
   assert table[directory+f'rank{rank}/timings.jsonl']['sha256']==request['rank_timing_sha256'][str(rank)]
  fixtures={name[len(directory):]:r['sha256'] for name,r in table.items() if name.startswith(directory+'step') and name.endswith('.bf16')}
  assert len(fixtures)==request['fixture_files']==min(count,8)*48 and canonical(fixtures)==request['fixture_inventory_sha256']
  oracle_root=P.parents[3]/entry['oracle_directory'];oracle_receipt=json.loads((oracle_root/'receipt.json').read_text())
  assert sha(oracle_root/'receipt.json')==entry['oracle_receipt_sha256']
  assert sha(oracle_root/'result.json')==oracle_receipt['result_sha256'] and json.loads((oracle_root/'result.json').read_text())['tokens']==request['tokens']
  assert sha(oracle_root/'validation.json')==oracle_receipt['validation_sha256'] and json.loads((oracle_root/'validation.json').read_text())['fixture_hashes']==fixtures
  state=table[directory+'state-evidence.json.gz'];retained=table[directory+'state-retention.json'];metadata=json.loads(retained['text'])
  assert state['sha256']==request['state_evidence_sha256']==metadata['sha256'] and retained['sha256']==request['state_retention_sha256']
  state_rows=json.loads(gzip.decompress(state['data']))['files'];states={r['path']:r for r in state_rows}
  assert len(states)==len(state_rows)==request['retained_state_files']==metadata['files']
  assert sum(r['bytes'] for r in state_rows)==metadata['original_bytes'] and state['bytes']==metadata['retained_bytes']
  for value in state_rows:
   if 'text' in value:assert hashlib.sha256(value['text'].encode()).hexdigest()==value['sha256'] and len(value['text'].encode())==value['bytes']
  for rank in (0,1):
   assert states[f'rank{rank}/request-state-inventory.json']['sha256']==request['runtime_state_inventory_sha256'][str(rank)]
   target=json.loads(states[f'rank{rank}/state-2147483647/state.json']['text'])
   for name,digest in target['buffers'].items():
    leaf=('alternate-'+name[len('alternate:'):] if name.startswith('alternate:') else name)+'.bin'
    assert states[f'rank{rank}/state-2147483647/{leaf}']['sha256']==digest
 assert row['token_count']==sum(r['token_count'] for r in requests) and row['fixture_files']==sum(r['fixture_files'] for r in requests)
 return {str(archive.relative_to(P)):sha(archive)}

def main():
 from build import sources
 names="""argument-block-tests.json argument-state-gates.json prepared-invalidation.json prepared-host-benchmark.json submission-overlay-gates.json review-prepared-gates.json p33-candidate-gates.json p33-linked-fixture-gates.json k2-admission-tests.json k2-selection-tests.json p38-k2-selection-tests.json p38-kernel-gates.json p38-qsa-capacity-gates.json p30-attention-cpu.json p30-small-cpu.json owner-gates.json fixture-gates.json validation-gates.json entry-codes.json window-tests.json identity-tree-tests.json kernel-sizes.json expert-down-review-gates.json state-machine-tests.json mtp-controller-tests.json review-controller-tests.json review-native-faults.json canary-host-gates.json resident-host-gates.json rollback-inventory.json draft-auth-gates.json pipeline-draft-agreement.json native-controller-cpu.json native-controller-asan.json native-controller-tsan.json native-mailbox-faults.json native-mailbox-faults-asan.json native-mailbox-faults-tsan.json native-mini-cpu.json receipt-metadata-gates.json suite-gate-results.json real-controller-gates.json review-resume-controller.json review-resume-reset.json review-resume-authority.json review-resume-storage-gates.json review-resume-window-storage-gates.json draft-window-cleanup-gates.json reset-retention-gate-results.json suite-export-retention-gates.json storage-race-gates.json suite-warmup-gates.json resume-input-integrity.json review-draft-capture.json window-cpu-fixtures.json window-cpu-models.json suite-real-cpu.json""".split()
 for c in ('gnu-host','icpx-host','asan'):names.extend([f'mini-{c}.json',f'mtp-gates-{c}.json'])
 for c,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  names.append(f'real-campaign-{c}.json')
  names.extend(f'real-{prefix}{m}.json' for m in ('none','ngram','hit','miss','mtp'))
 names.extend(f'real-native-{m}.json' for m in ('none','ngram','hit','miss','mtp'))
 prompts=('incident-retrospective','code-review','customer-email','benchmark-analysis')
 names.extend(f'agreement-{n}.json' for n in prompts)
 gates={n:json.loads((P/n).read_text()) for n in names}
 for n,r in gates.items():
  assert r.get('passed',r.get('source_review_passed')) is True,('gate incomplete',n)
  for field in ('source_sha256','sources_sha256'):
   if isinstance(r.get(field),dict):
    for source,digest in r[field].items():assert sha(P/source)==digest,('stale gate source',n,source)
 entries=('p33-linked-fixtures','own-rt-iq3','nongemv-fixtures','k2-fixtures','jit-smoke','authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests','prepared-invalidation-tests')
 binaries={str(f.relative_to(B)):sha(f) for c in ('gnu-host','icpx-host','asan','device') for f in (B/c).iterdir() if f.name in entries}
 # Native controller and reset evidence must name this exact final host binary.
 host_sha=binaries['gnu-host/own-rt-iq3']
 mini=gates['native-mini-cpu.json']
 assert mini['binary_sha256']==host_sha and mini['cases']==1109 and mini['exhaustive_ternary_patterns']==1093
 assert mini['long_random_cases']==12 and mini['long_random_tokens']==64 and mini['host_memory']=='resident' and mini['host_path']=='prepared'
 assert gates['receipt-metadata-gates.json']['gates']==10
 suite=gates['suite-gate-results.json'];assert suite['binary_sha256']==host_sha
 proofs=suite['reset_proofs'];assert len(proofs)==4 and {(r['controller'],r['draft']) for r in proofs}=={(c,d) for c in ('python','native') for d in ('none','mtp')}
 for proof in proofs:
  assert proof['exact'] is True and proof['prompts']>=3 and proof['orders']>=2 and proof['host_memory']=='resident' and proof['host_path']=='prepared' and proof['argument_audit'] is True
  evidence=proof['prompt_evidence'];assert len(evidence)>=3 and len({r['prompt_id'] for r in evidence})==len(evidence)
  for row in evidence:
   digests=row['canonical_sha256_by_order'];assert len(digests)>=2 and len(set(digests))==1 and row['fixture_files']==32 and row['state_files']>=(214 if proof['draft']=='mtp' else 208)
 assert suite['formula_test'] and suite['checker_snapshot_binding'] and suite['exactness_failure_continues']==[False,True,True]
 suite_archives=bind_cpu_suite(gates['suite-real-cpu.json'],host_sha)
 # Independent resumed reviews bind the source, dynamic gates bind the binaries.
 for name in ('review-resume-controller.json','review-resume-reset.json','review-resume-authority.json','review-draft-capture.json'):
  review=gates[name];assert review['source_sha256']
  for source,digest in review['source_sha256'].items():assert sha(P/source)==digest,('stale independent review',name,source)
 # Hash-bind both the gate executions and the standalone sanitizer builds.
 native_build=json.loads((P/'native-build-receipt.json').read_text());native_rows={r['binary']:r for r in native_build['binaries']}
 for gate,entry,count_field,count in (
  ('native-controller-cpu.json','native-controller-test','cases',1123),('native-controller-asan.json','native-controller-asan','cases',1123),('native-controller-tsan.json','native-controller-tsan-llvm22','cases',1123),
  ('native-mailbox-faults.json','native-mailbox-fault-test','gates',5),('native-mailbox-faults-asan.json','native-mailbox-fault-asan','gates',5),('native-mailbox-faults-tsan.json','native-mailbox-fault-tsan-llvm22','gates',5)):
  digest=sha(B/entry);row=native_rows['build/'+entry]
  assert gates[gate]['binary_sha256']==digest==row['sha256'] and gates[gate][count_field]==count
  if count_field=='cases':assert gates[gate]['ternary_patterns']==1093 and gates[gate]['long_random_cases']==24 and gates[gate]['bounded_spin_iterations']==0
  else:assert gates[gate]['repeated_requests']==32 and gates[gate]['spin_iterations']==0
  assert row['compile_and_link_same_invocation'] is True and all(flag in row['command'] for flag in ('-fno-fast-math','-ffp-contract=off'))
  for source,expected in row['source_sha256'].items():assert sha(P/source)==expected,('stale controller build',entry,source)
  binaries[entry]=digest
 for phase in ('fixtures','models'):assert gates['window-cpu-'+phase+'.json']['binary_sha256']==host_sha
 fixtures={r['window']:r for r in gates['window-cpu-fixtures.json']['rows']}
 for name in ('K1a','K1b'):
  assert fixtures[name]['fixture_binary_sha256']==binaries['gnu-host/nongemv-fixtures'] and fixtures[name]['linked_binary_sha256']==binaries['gnu-host/p33-linked-fixtures']
 assert fixtures['K2']['fixture_binary_sha256']==binaries['gnu-host/k2-fixtures']
 assert gates['argument-block-tests.json']['checks']==16 and gates['prepared-invalidation.json']['tests']==15
 for c in ('gnu-host','icpx-host','asan'):
  for prefix in ('mini-','mtp-gates-'):assert gates[prefix+c+'.json']['binary_sha256']==binaries[c+'/own-rt-iq3']
 for c,prefix in (('gnu-host',''),('icpx-host','icpx-host-')):
  for m in ('none','ngram','hit','miss','mtp'):
   r=gates[f'real-{prefix}{m}.json'];assert r['binary_sha256']==binaries[c+'/own-rt-iq3'] and r['token_matches']==8 and r['layer_matches']==r['layer_total']==384
 native_archives={};native_rows=gates['real-controller-gates.json']['rows']
 assert len(native_rows)==5 and {r['mode'] for r in native_rows}=={'none','ngram','hit','miss','mtp'}
 for mode in ('none','ngram','hit','miss','mtp'):
  native=gates[f'real-native-{mode}.json'];reference=gates[f'real-{mode}.json']
  assert native==next(r for r in native_rows if r['mode']==mode),'native aggregate differs from mode receipt'
  assert native['device_executed'] is False and native['binary_sha256']==host_sha and native['tokens']==8 and native['fixtures']==384
  assert native['python_receipt_sha256']==sha(P/f'real-{mode}.json'),'native comparison used stale Python receipt'
  archive,table=archived_run(native['root']);actual,signature=native_signature(table)
  assert table['receipt.json']['sha256']==native['native_receipt_sha256'],'native archived receipt changed'
  assert actual['passed'] is True and actual['device_executed'] is False and actual['binary_sha256']==host_sha and actual['controller']=='native'
  assert actual['draft']==('script' if mode in ('hit','miss') else mode)
  assert signature==reference['controller_signature'],'native tokens/guesses/state/fixtures differ'
  assert len(signature['tokens'])==8 and len(signature['fixtures'])==384 and signature['counts']==native['stats']
  assert {name.split('/',1)[1]:digest for name,digest in signature['fixtures'].items()}==reference['fixture_sha256']
  if mode=='mtp':assert signature['draft_final_state'],'missing native draft state'
  if mode in ('hit','miss'):assert signature['counts']['guesses']==7 and signature['counts']['hits']==(7 if mode=='hit' else 0)
  native_archives[str(archive.relative_to(P))]=sha(archive)
 for n in prompts:assert gates[f'agreement-{n}.json']['binary_sha256']==binaries['gnu-host/own-rt-iq3']
 for row in gates['fixture-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/nongemv-fixtures']
 for row in gates['p33-linked-fixture-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/p33-linked-fixtures']
 for row in gates['owner-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['name']]
 for row in gates['validation-gates.json']['checks']:
  if 'entry' in row:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['entry']]
 for n in ('review-native-faults.json','draft-auth-gates.json'):assert gates[n]['binary_sha256']==binaries['gnu-host/own-rt-iq3']
 archived=gates['fixture-gates.json']['full_receipts'];blob=P/archived['path'];assert sha(blob)==archived['compressed_sha256']
 assert hashlib.sha256(gzip.decompress(blob.read_bytes())).hexdigest()==archived['uncompressed_sha256']
 precision={};links={}
 for c in ('gnu-host','icpx-host','asan','device'):
  flags=['-fno-fast-math','-ffp-contract=off']+(['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'] if c=='device' else [])
  cc=json.loads((B/c/'compile_commands.json').read_text());ll={str(f.relative_to(B)):f.read_text() for f in (B/c).rglob('link.txt')}
  assert cc and ll and all(all(x in r['command'].split() for x in flags) for r in cc) and all(all(x in v.split() for x in flags) for v in ll.values())
  precision[c]=dict(flags=flags,compile_count=len(cc),link_count=len(ll),compile_commands_sha256=sha(B/c/'compile_commands.json'));links.update(ll)
 from math_gate import check
 from queue_gate import check as queuecheck
 official=json.loads((P/'official-tensors.json').read_text())
 capture_inputs={};capture_fixtures={}
 for prompt in prompts:
  run=json.loads((P/f'capture-run-{prompt}.json').read_text());assert run['passed'] and run['binary_sha256']==host_sha
  root=Path(run['output']);expected=json.loads((P/f'capture-repeat-{prompt}.json').read_text())['sha256']
  actual={str(f.relative_to(root)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in root.glob(pattern)}
  assert actual and actual==expected
  capture_inputs[prompt]=sha(P/f'capture-input-{prompt}.json');capture_fixtures[prompt]=actual
 admission=None
 if (P/'window-seal-admission-gates.json').exists():
  admission=json.loads((P/'window-seal-admission-gates.json').read_text());assert admission['passed']
  names.append('window-seal-admission-gates.json')

 receipt=dict(schema='own-runtime.iq3.packet38.build.v1',passed=True,device_executed=False,real_model_device_qualified=False,
  source_parents={'packet32':'2e8ec7585c0b0fdd24c7aa07e5752167d6ff2637','packet36':'3048343bff','packet37':'3c03e29a4e'},arithmetic='iq3-p17-detmath-v2',
  sources=sources(),artifacts_sha256=binaries,precision=precision,link_commands=links,input_sha256=sha(B/'input/input.json'),
  nongemv_fixture_host_sha256=gates['fixture-gates.json']['output_sha256'],
  p33_linked_fixture_host_sha256=gates['p33-linked-fixture-gates.json']['output_sha256'],
  draft_capture_fixture_sha256=capture_fixtures,draft_capture_input_sha256=capture_inputs,
  official_manifest_sha256=sha(P/'mtp-manifest.tsv'),official_tensor_receipt_sha256=sha(P/'official-tensors.json'),
  official_tensor_sha256={n:r['sha256'] for n,r in official['tensors'].items()},gate_receipts={n:sha(P/n) for n in names},native_build_receipt_sha256=sha(P/'native-build-receipt.json'),
  math_gate=check(),queue_gate=queuecheck(),memory_plan=json.loads((P/'memory-plan.json').read_text()),
  native_controller_archive_sha256=native_archives,suite_execution_archive_sha256=suite_archives,
  max_compile_jobs=2,numeric_threads_per_rank=2,max_cpu_bound_processes=4,anonymous_memory_limit_bytes=10000000000,
  pending=['all coordinator device windows','device kernel timing and K2 selection','GPU controller equivalence and latency','complete twelve-prompt suite when all oracles arrive'])
 if admission is not None:
  # A passed rehearsal binds the current consumer code AND the exact seal
  # subset it consumed. Gate-receipt hashes are outside that subset, so final
  # resealing after rehearsal does not create a circular receipt hash.
  from test_window_seal_admission import contract
  required_sources={'window.py','fixture_support.py','draft_window.py','test_window_seal_admission.py'}
  assert set(admission['source_sha256'])==required_sources,'admission source coverage'
  for source,digest in admission['source_sha256'].items():
   assert sha(P/source)==digest,('stale window admission source',source)
  consumed=contract(receipt)
  assert admission['seal_fields']==list(consumed),'admission seal field coverage'
  digest=hashlib.sha256(json.dumps(consumed,sort_keys=True).encode()).hexdigest()
  assert admission['consumed_seal_sha256']==digest,'window admission consumed a different seal'
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'cpu-tests.json').write_text(json.dumps(dict(passed=True,device_executed=False,gate_count=len(names),gates=receipt['gate_receipts']),indent=2)+'\n')
 (P/'BINARY-HASHES.md').write_text('# Binary SHA256\n\nNo device binary ran. Ignored build trees remain for coordinator windows.\n\n| Binary | SHA256 |\n| --- | --- |\n'+''.join(f'| {n} | {h} |\n' for n,h in sorted(binaries.items())))
 print('SEALED',len(names),'CPU gate receipts;',len(binaries),'binaries')
if __name__=='__main__':main()
