"""Apply the packet181 entry-TU native delta and harness edits (idempotent, fail-closed).

Native delta: start from packet180's patched main.cpp (path-normalized to packet165's tree,
exactly the form packet180's adapt wrote and its native-delta.json pins), apply the packet181
edit (every request's result.json records its prompt positions and prompt mechanism) and install
the packet-root checkpoint.hpp v3 (label "qualified-one-card" + qualified_by, v1.2+p181 contract,
read-compatible with packet180's v1.2+p180 "experimental" manifests, prefill/append path record).
Kernel arithmetic untouched: build_checkpoint.py relinks every kernel object byte-identical from
packet165, exactly as packet179 and packet180 did.

No chunked/batched prefill is added: the engine has one prompt mechanism (one position per step
through the prompt step), already used identically by fresh prompts and by packet180's append;
see README "Append prefill: what the engine does".

Harness edits (re-copied from packet180 first so reruns are idempotent): worker lifecycle uses
the packet181 analyzer (measurement.lifecycle_check_v3, built on packet180's unchanged
lifecycle_check) with the per-position prefill rows; measurement gains the v3 analyzer,
contract table and prefill observation; screen's lifecycle summary carries the label and the
not-claimed list; entry help text; budget notes. lifecycle.json and reference-p179-row-a.json
are inherited unchanged (row b's structure and row a's reference are packet180's).
"""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
OLD180=P.parent/'packet180-session-swap-v2'
OLD165=P.parent/'packet165-warm-prefill'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def sha_text(t):return hashlib.sha256(t.encode()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')

NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
MAIN=P/'one-card'/NAT/'main.cpp'

def replace_once(text,old,new,what):
 assert text.count(old)==1,('anchor',what,text.count(old))
 return text.replace(old,new,1)

def native_edits(text):
 # 1. result.json: the prompt positions this process stepped and the mechanism (one exists).
 old='    const std::string checkpoint_json=pipeline::checkpoint_result_json(restoring?&restored:nullptr,checkpoint_restore_ms,append_prefill_ms,saving?&saved:nullptr);\n'
 new=r'''    // packet181: record the prompt positions this process stepped and how. This engine has one
    // prompt mechanism ("incremental": one position per step through the prompt step above), used
    // identically for a fresh prompt [0, len) and for appended tokens [N, len) after a restore;
    // a same-generation resume steps no prompt position.
    const size_t prefill_first=restoring?size_t(restored.position):0;
    const size_t prefill_tokens=restoring?(appending?input.size()-prefill_first:0):input.size();
    const std::string checkpoint_json=pipeline::checkpoint_result_json(restoring?&restored:nullptr,checkpoint_restore_ms,append_prefill_ms,saving?&saved:nullptr,
      prefill_ms,prefill_first,prefill_tokens);
'''
 return replace_once(text,old,new,'result checkpoint json')

# ---------------------------------------------------------------- harness blocks
WORKER_DOC_OLD='packet180: kind lifecycle is the experimental append / restore-then-save gate (row b).\n'
WORKER_DOC_NEW=('packet180: kind lifecycle is the append / restore-then-save gate (row b).\n'
 'packet181: the same row; manifests carry label qualified-one-card (contract v1.2+p181), every leg\n'
 'records its prompt path, and the append prefill cost is reported against the cold reference.\n')
WORKER_INIT_OLD=" results={};receipts=[]\n"
WORKER_INIT_NEW=" results={};receipts=[];prefill={}\n"
WORKER_STREAM_OLD="   if spec['leg']!='resume-s2':streams['prefill-timings.jsonl']=measurement.check_file_stream(dest/'prefill-timings.jsonl')\n"
WORKER_STREAM_NEW=(WORKER_STREAM_OLD+
 "   prefill[spec['leg']]=measurement.prefill_rows(dest/'prefill-timings.jsonl')  # packet181: per-position prompt-step rows\n")
WORKER_CHECK_OLD=" check=measurement.lifecycle_check(results,manifests,tools,L,prompt,turn,p179,oracle)\n"
WORKER_CHECK_NEW=" check=measurement.lifecycle_check_v3(results,manifests,tools,L,prompt,turn,p179,oracle,prefill)\n"
WORKER_SCOPE_OLD="  scope='experimental session checkpoint lifecycle: append, restore-then-save, chain resume and repeat determinism versus a one-shot fresh reference of the same input; oracle cap 128 on the save leg; not a performance claim'))\n"
WORKER_SCOPE_NEW=("  scope='session checkpoint lifecycle (manifest label qualified-one-card, contract v1.2+p181): append, restore-then-save, chain resume and repeat determinism "
 "versus a one-shot fresh reference of the same input; every leg records its prompt path; oracle cap 128 on the save leg; the append prefill timing is a reported observation, "
 "not a gate and not a performance claim; one card only, TP2 checkpoints not implemented, no ctxkeeper adapter'))\n")

MEASUREMENT_APPEND=r'''
# ---------------------------------------------------------------- packet181 analyzer (v3)
# packet180's lifecycle_check above is kept byte-for-byte and is the base of lifecycle_check_v3.
QUALIFIED_BY={'scope':'one card (tp1-full512 profile) only; TP2 checkpoints not implemented; no ctxkeeper adapter yet',
 'device_gates':[{'packet':'packet179-session-swap','date':'2026-10-22','operations':['same-generation-resume']},
                 {'packet':'packet180-session-swap-v2','date':'2026-10-22','operations':['append','restore-then-save']}]}
CONTRACTS={'v1.2+p181':dict(label='qualified-one-card',packet='packet181-session-swap-v3',qualified_by=QUALIFIED_BY),
           'v1.2+p180':dict(label='experimental',packet='packet180-session-swap-v2',qualified_by=None)}
ENGINE_PREFILL_PATH='incremental'   # the engine's only prompt mechanism: one position per prompt step
APPEND_PREFILL_RATE_BOUND=1.25      # reported bound on append ms/token over cold ms/token; never a gate
NOT_CLAIMED=['one card (tp1-full512 profile) only',
 'TP2 (two-card) checkpoints are not implemented',
 'no ctxkeeper adapter yet: ctxkeeper does not call these operations',
 'model identity is host-local (stat pins); not portable across hosts',
 'no chunked/batched prefill: appended tokens and fresh prompts are both stepped one position at a time',
 'append prefill timing is an observation of fresh processes, not a performance claim']

def prefill_rows(path):
 """Per-position prompt-step rows of one native prefill-timings.jsonl as [token_index, wall_ms]."""
 rows=[]
 for line in Path(path).read_text().splitlines():
  row=json.loads(line)
  if row.get('kind')!='prefill_token':continue
  require(type(row.get('token_index')) is int and type(row.get('wall_ms')) in (int,float) and math.isfinite(row['wall_ms']),'malformed prefill row')
  rows.append([row['token_index'],float(row['wall_ms'])])
 require([i for i,_ in rows]==list(range(rows[0][0],rows[0][0]+len(rows))) if rows else True,'prefill rows are not consecutive positions')
 return rows

def append_prefill_path(result):
 """(path, source) of an append leg. packet180 receipts have no such field: their append stepped the
 same per-position prompt step, so a missing field reads as 'incremental' (legacy)."""
 rr=(result.get('checkpoint') or {}).get('restore') or {}
 if 'append_prefill_path' in rr:return rr['append_prefill_path'],'recorded'
 return ENGINE_PREFILL_PATH,'legacy: field absent (packet180 receipt), read as incremental'

def fresh_prefill_path(result):
 pf=(result.get('checkpoint') or {}).get('prefill')
 if pf is not None:return pf.get('path'),'recorded'
 return ENGINE_PREFILL_PATH,'legacy: field absent (packet180 receipt), read as incremental'

def prefill_observation(results,spec,prompt,turn,prefill=None):
 """Reported, never gated: append prefill cost per token versus the cold one-shot prefill, at the
 overall rate (brief bound x1.25) and at matched expert-cache warmth (first prompt steps of a
 fresh process in both)."""
 N1=len(prompt)+spec['K']-1;L=len(prompt)+spec['K']+len(turn)
 r=results['reference'];ms=r.get('prefill_ms')
 cold=dict(ms=ms,tokens=L,ms_per_token=ms/L if type(ms) in (int,float) and ms>0 else None,
  definition='reference process prefill_ms (all L input positions from a reset state, through the first generated token) / L')
 legs={}
 for leg in ('append-s2','append-s2b'):
  rr=(results[leg].get('checkpoint') or {}).get('restore') or {}
  ams=rr.get('append_prefill_ms');tokens=rr.get('append_prefill_tokens',L-N1)
  row=dict(ms=ams,tokens=tokens,tokens_source='recorded' if 'append_prefill_tokens' in rr else 'derived: L - N (packet180 receipt)',
   ms_per_token=ams/tokens if type(ams) in (int,float) and tokens else None)
  row['ratio_to_cold_per_token']=row['ms_per_token']/cold['ms_per_token'] if row['ms_per_token'] and cold['ms_per_token'] else None
  row['within_bound']=None if row['ratio_to_cold_per_token'] is None else row['ratio_to_cold_per_token']<=APPEND_PREFILL_RATE_BOUND
  a=(prefill or {}).get(leg);ref=(prefill or {}).get('reference')
  if a and ref:
   steps=len(a);append_ms=sum(w for _,w in a)
   first=sum(w for _,w in ref[:steps]);same=[w for i,w in ref if a[0][0]<=i<a[0][0]+steps]
   row['matched_warmth']=dict(prompt_steps=steps,append_ms=append_ms,reference_first_steps_ms=first,ratio=append_ms/first if first else None,
    definition='sum of per-position prompt-step wall_ms (prefill-timings.jsonl): the append process at positions [N, L-1) versus the reference process at its first positions [0, L-1-N); both are the first prompt steps of a fresh process with an empty expert cache')
   row['same_positions']=dict(reference_ms=sum(same),ratio=append_ms/sum(same) if same else None,
    definition='the reference process at the same positions [N, L-1), where its expert cache is already warm from positions [0, N)')
  legs[leg]=row
 return dict(gated=False,bound=APPEND_PREFILL_RATE_BOUND,cold=cold,append=legs,
  bound_definition='append_prefill_ms / append_prefill_tokens <= 1.25 x cold ms/token; reported, never a gate',
  interpretation='appended tokens and fresh prompt tokens go through the same per-position prompt step; a fresh process pays its empty expert cache on its first prompt positions, which the append spends on 127 positions and the cold reference amortizes over 469')

def lifecycle_check_v3(results,manifests,tools,spec,prompt,turn,p179_tokens,oracle,prefill=None,expect='v1.2+p181'):
 """Row b gates for packet181. Base: packet180's lifecycle_check (unchanged); its three
 'manifest identity' gates are re-evaluated for the expected contract (label, contract,
 qualified_by, engine packet). Added: the append prompt path equals the fresh reference's and the
 engine's only mechanism; for v1.2+p181 receipts, the prefill/append records. Never raises on a
 gate failure, so both streams stay in the receipt."""
 require(expect in CONTRACTS,'unknown contract '+str(expect))
 want=CONTRACTS[expect];ids=spec['checkpoint_ids']
 base=lifecycle_check(results,manifests,tools,spec,prompt,turn,p179_tokens,oracle)
 gates=dict(base['gates'])
 replaced=sorted(k for k in gates if k.startswith('manifest identity '))
 for k in replaced:gates.pop(k)
 def gate(name,ok,detail=None):gates[name]=dict(passed=bool(ok),detail=detail)
 for cid in (ids['S1'],ids['S2'],ids['S2b']):
  mm=manifests[cid]['manifest']
  ok=(mm.get('format')=='ownrt.session-checkpoint.v1' and mm.get('label')==want['label'] and mm.get('contract')==expect
      and mm.get('operations')==LIFECYCLE_OPERATIONS and mm.get('checkpoint_id')==cid
      and ('qualified_by' in mm)==(want['qualified_by'] is not None) and mm.get('qualified_by')==want['qualified_by']
      and (mm.get('engine') or {}).get('packet')==want['packet'])
  gate('manifest identity '+cid,ok,dict(label=mm.get('label'),contract=mm.get('contract'),qualified_by=mm.get('qualified_by'),
   engine_packet=(mm.get('engine') or {}).get('packet'),expected=dict(label=want['label'],contract=expect,packet=want['packet'])))
 ref_path,ref_source=fresh_prefill_path(results['reference'])
 paths=dict(reference=dict(path=ref_path,source=ref_source))
 for leg in ('append-s2','append-s2b'):
  path,source=append_prefill_path(results[leg]);paths[leg]=dict(path=path,source=source)
  gate('append prefill path '+leg,path==ref_path==ENGINE_PREFILL_PATH,dict(append=path,reference=ref_path,engine_mechanism=ENGINE_PREFILL_PATH,source=source))
 records='not evaluated: packet180 receipts predate the prefill/append record fields'
 if expect=='v1.2+p181':
  records='evaluated'
  N1=len(prompt)+spec['K']-1;L=len(prompt)+spec['K']+len(turn)
  def ck(leg):return results[leg].get('checkpoint') or {}
  for leg in ('append-s2','append-s2b'):
   c=ck(leg);rr=c.get('restore') or {};pf=c.get('prefill') or {}
   gate('append prefill record '+leg,c.get('label')==want['label'] and c.get('contract')==expect and rr.get('append_prefill_tokens')==L-N1
        and rr.get('append_prefill_path')==pf.get('path')==ENGINE_PREFILL_PATH and pf.get('first_position')==N1 and pf.get('tokens')==L-N1
        and pf.get('ms')==rr.get('append_prefill_ms')==results[leg].get('prefill_ms'),
        dict(prefill=pf,append_prefill_tokens=rr.get('append_prefill_tokens'),append_prefill_path=rr.get('append_prefill_path'),append_prefill_ms=rr.get('append_prefill_ms')))
  c=ck('reference');pf=c.get('prefill') or {}
  gate('reference prefill record',c.get('label')==want['label'] and pf.get('path')==ENGINE_PREFILL_PATH and pf.get('first_position')==0
       and pf.get('tokens')==L and pf.get('ms')==results['reference'].get('prefill_ms'),pf)
  c=ck('save-s1');pf=c.get('prefill') or {}
  gate('save prefill record',c.get('label')==want['label'] and pf.get('path')==ENGINE_PREFILL_PATH and pf.get('first_position')==0
       and pf.get('tokens')==len(prompt),pf)
  c=ck('resume-s2');pf=c.get('prefill') or {};rr=c.get('restore') or {}
  gate('resume prefill record',c.get('label')==want['label'] and pf.get('path') is None and pf.get('tokens')==0
       and rr.get('append_prefill_tokens')==0 and rr.get('append_prefill_path') is None,dict(prefill=pf,restore_path=rr.get('append_prefill_path')))
 problems=[k for k,v in gates.items() if not v['passed']]
 out=dict(base)
 out.update(passed=not problems,problems=problems,gates=gates,contract_expected=expect,label_expected=want['label'],
  qualified_by_expected=want['qualified_by'],record_gates=records,
  base_analyzer='packet180 measurement.lifecycle_check (unchanged); its three manifest identity gates are re-evaluated for the expected contract',
  replaced_base_gates=replaced,base_passed=base['passed'],base_problems=base['problems'],
  prefill_paths=paths,prefill_observation=prefill_observation(results,spec,prompt,turn,prefill),not_claimed=NOT_CLAIMED)
 return out
'''

SCREEN_REPORT_OLD="""   strict512=False,submission_eligible=False,experimental_checkpoint=True)
"""
SCREEN_REPORT_NEW="""   strict512=False,submission_eligible=False,experimental_checkpoint=False,checkpoint_label=receipt.get('label_expected'),
   checkpoint_contract=receipt.get('contract_expected'),not_claimed=receipt.get('not_claimed'))
"""
SCREEN_PLAN_OLD="""    legs=['save-s1','append-s2','resume-s2','reference','append-s2b'],experimental=True,
"""
SCREEN_PLAN_NEW="""    legs=['save-s1','append-s2','resume-s2','reference','append-s2b'],label='qualified-one-card',contract='v1.2+p181',
"""
SCREEN_GATE_OLD="save leg == packet179 row a [0:K] and oracle-128; inspect/delete tools; a divergence fails with the first index and both streams'))"
SCREEN_GATE_NEW=("save leg == packet179 row a [0:K] and oracle-128; inspect/delete tools; manifests labelled qualified-one-card (v1.2+p181, qualified_by); "
 "append prompt path == the reference prompt path == incremental; append prefill vs cold per token reported, not gated; a divergence fails with the first index and both streams'))")
ENTRY_OLD="lifecycle is the experimental append/restore-then-save gate')"
ENTRY_NEW="lifecycle is the append/restore-then-save gate (packet181: label qualified-one-card)')"

def main():
 p=P/'one-card'
 parent_main=(OLD165/'one-card'/NAT/'main.cpp').read_text()
 p180_delta=json.loads((OLD180/'one-card/evidence/native-delta.json').read_text())
 p180_main=(OLD180/'one-card'/NAT/'main.cpp').read_text().replace(str(OLD180),str(OLD165))
 assert sha_text(parent_main)==p180_delta['parent_main_sha256'],'packet165 parent main.cpp drifted'
 assert sha_text(p180_main)==p180_delta['patched_main_sha256'],'packet180 patched main.cpp drifted'
 p180_header=(OLD180/'checkpoint.hpp').read_text()
 assert sha_text(p180_header)==p180_delta['checkpoint_hpp_sha256'],'packet180 checkpoint.hpp drifted'
 text=native_edits(p180_main)
 MAIN.write_text(text)   # packet165-path-normalized form; build_checkpoint.py relocates to this packet
 header=(P/'checkpoint.hpp').read_text()
 (MAIN.parent/'checkpoint.hpp').write_text(header)
 lineage=p/'lineage'
 (lineage/'packet181-native-delta.patch').write_text(''.join(difflib.unified_diff(
  parent_main.splitlines(True),text.splitlines(True),fromfile='packet165/'+NAT+'/main.cpp',tofile='packet181/'+NAT+'/main.cpp')))
 (lineage/'packet181-vs-packet180-main.patch').write_text(''.join(difflib.unified_diff(
  p180_main.splitlines(True),text.splitlines(True),fromfile='packet180/'+NAT+'/main.cpp',tofile='packet181/'+NAT+'/main.cpp')))
 (lineage/'packet181-vs-packet180-checkpoint.patch').write_text(''.join(difflib.unified_diff(
  p180_header.splitlines(True),header.splitlines(True),fromfile='packet180/'+NAT+'/checkpoint.hpp',tofile='packet181/'+NAT+'/checkpoint.hpp')))

 # ---- harness edits (re-copied from packet180 first so reruns are idempotent)
 for leaf in ('worker.py','measurement.py','screen.py','entry.py','budget.json'):
  src=(OLD180/'one-card'/leaf).read_text()
  if leaf.endswith('.py'):src=src.replace(OLD180.name,P.name)
  (p/leaf).write_text(src)
 worker=(p/'worker.py').read_text()
 for old,new,what in ((WORKER_DOC_OLD,WORKER_DOC_NEW,'worker doc'),(WORKER_INIT_OLD,WORKER_INIT_NEW,'worker init'),
                      (WORKER_STREAM_OLD,WORKER_STREAM_NEW,'worker prefill rows'),(WORKER_CHECK_OLD,WORKER_CHECK_NEW,'worker analyzer'),
                      (WORKER_SCOPE_OLD,WORKER_SCOPE_NEW,'worker scope')):
  worker=replace_once(worker,old,new,what)
 (p/'worker.py').write_text(worker)
 (p/'measurement.py').write_text((p/'measurement.py').read_text()+MEASUREMENT_APPEND)
 screen=(p/'screen.py').read_text()
 for old,new,what in ((SCREEN_REPORT_OLD,SCREEN_REPORT_NEW,'screen report'),(SCREEN_PLAN_OLD,SCREEN_PLAN_NEW,'screen plan'),(SCREEN_GATE_OLD,SCREEN_GATE_NEW,'screen gate')):
  screen=replace_once(screen,old,new,what)
 (p/'screen.py').write_text(screen)
 (p/'entry.py').write_text(replace_once((p/'entry.py').read_text(),ENTRY_OLD,ENTRY_NEW,'entry kind'))
 budget=json.loads((p/'budget.json').read_text())
 budget['lifecycle_note']=('row b writes S1 (~69 MB at N=342), S2 and S2b (~76 MB each at N=596) plus five native output folders (packet180 device: '
  '68,756,516 and 75,975,716 B); S2b blobs are deleted by the delete-tool gate; 400 MB planned writes cover both rows; floors unchanged')
 budget['expected_seconds_note']=('informational estimates from packet180 device receipts (row a 500 s; row b 1167 s: five model loads of 209-215 s plus '
  '4.5-38 s requests and the host tools); no runner enforces them; the enforced bound is the 7200 s screen supervision of the worker child (screen.py)')
 save(p/'budget.json',budget)

 save(p/'evidence/native-delta.json',dict(passed=True,device_executed=False,
  entry_tu_only=True,patched=[NAT+'/main.cpp',NAT+'/checkpoint.hpp'],added=[],
  parent_main_sha256=sha_text(parent_main),packet180_main_sha256=sha_text(p180_main),
  patched_main_sha256=sha_text(text),checkpoint_hpp_sha256=sha(MAIN.parent/'checkpoint.hpp'),
  packet180_checkpoint_hpp_sha256=sha_text(p180_header),
  patch_sha256=sha(lineage/'packet181-native-delta.patch'),
  incremental_main_patch_sha256=sha(lineage/'packet181-vs-packet180-main.patch'),
  incremental_checkpoint_patch_sha256=sha(lineage/'packet181-vs-packet180-checkpoint.patch'),
  harness_files=['worker.py','measurement.py','screen.py','entry.py','budget.json'],
  new_files=[],
  kernel_arithmetic='unchanged by construction: only the entry TU textual closure changed; kernel objects relinked byte-identical from packet165 by build_checkpoint.py',
  prefill_mechanism='unchanged: no chunked/batched prefill exists in this engine; fresh prompts and appended tokens use the same per-position prompt step (recorded as incremental)',
  scope='session checkpoint v3: manifest label qualified-one-card + qualified_by (contract v1.2+p181), read compatibility with packet180 v1.2+p180 experimental manifests, prefill/append path record in result.json; device qualification of this binary pending'))
 print('packet181 native delta + harness edits applied')

if __name__=='__main__':main()
