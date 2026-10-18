from pathlib import Path
import json,hashlib,shutil
R=Path('/home/steve/llm-optimizations');P=R/'experiments/own-xpu-runtime/stage2/packet114-draft-prefix';T=P.parent/'packet109-other-fusion';BASE=P.parent/'packet103-record-bundle';N=80128
assert not (P/'source-copy-provenance.json').exists(), 'one-shot historical constructor; use committed sources'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Copy wrapper/code infrastructure, not any parent results or model artifacts.
leaves=['ab.py','bracket.py','bracket_config.py','bracket_job.py','build_engine.py','common.py','compare.py','conditions.py','cpu_seal.py','devices.py','drain_gate.py','fault_review.py','full_shape.py','lane_admission.py','mini_selection.py','native_source.py','placement.py','plan_placements.py','protocol_gate.py','queue_plan.py','quick_seal.py','recipe.py','reset_gate.py','retain_shape.py','screen.py','seal_native.py','startup109.py','tp2_worker.py','window_adapter.py','audit_sources.py','chain_devices.py']
leaves+=['reference.json','integration.patch','screen-integration.patch','placements.json','chain-reference.json','chain-window-drain.patch','CHAIN-PATCH.md','v4-copy-provenance.json','placement-jobs.txt']
leaves+=['test_bracket.py','test_bracket_reporting.py','test_devices.py','test_lane_admission.py','test_placement.py','test_plan_admission.py','test_refusal.py','test_reporting.py','test_v3.py']
for leaf in leaves:
 t=(T/leaf).read_text().replace('packet109-other-fusion','packet114-draft-prefix').replace('packet109','packet114').replace('p109','p114').replace('startup109','startup114')
 (P/leaf.replace('109','114')).write_text(t)
for d in ['build','native','lineage','configs','placement-validation']:(P/d).mkdir(exist_ok=True)
(P/'predecessor-wrapper-seal.json').write_bytes((T/'wrapper-seal.json').read_bytes())
for f in (T/'native').glob('*'):
 (P/'native'/f.name).write_text(f.read_text().replace('109','114'))
pins={}
for f in (BASE/'build/checked').rglob('*'):
 if not f.is_file():continue
 target=P/'sources'/f.relative_to(BASE/'build/checked');target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(f.read_text().replace(str(BASE/'build/checked'),str(P/'sources')));pins[str(f.relative_to(R))]=sha(f)
(P/'source-copy-provenance.json').write_text(json.dumps({'packet103':pins,'post_fix_commit':'932df6642','wrapper_parent':{str((T/x).relative_to(R)):sha(T/x) for x in leaves}},indent=2)+'\n')
C=P/'sources'/BASE.relative_to(R)
f=C/'p83_head.hpp';t=f.read_text().replace(' if(choice=="coverage990")return 80128;',' if(choice=="p114-80128")return 80128;\n if(choice=="coverage990")return 80128;');f.write_text(t)
f=C/'p59c_select.hpp';t=f.read_text().replace('value!="production"&&value!="coverage990"','value!="production"&&value!="p114-80128"&&value!="coverage990"');f.write_text(t)
# No arithmetic changes. Only runtime prefix dispatch and draft recapture.
f=P/'native/engine_bracket.hpp';t=f.read_text().replace('if(true)require','if(key!="head_prefix")require').replace('if(key!="other_fusion")','if(true)').replace('      domain(selection->choices,"other_fusion",{"production","fused"});','      domain(selection->draft,"head_prefix",{"production","p114-80128"});\n      domain(selection->draft,"head_format",{"production"});');f.write_text(t)
f=P/'full_shape.py';t=f.read_text();start=t.index('    t=once(t,\'class Engine final\',');end=t.index('    t=once(t,\'  void guard() {\'',start);t=t[:start]+t[end:];f.write_text(t)
f=P/'native/full_shape_entry.cpp';t=f.read_text().replace('route==(choices.at("other_fusion")=="production")','route==(choices.at("route")=="route-fast")');start=t.index('  unsigned fused_routes=');end=t.index('  census(*e,a.output/',start);t=t[:start]+'''  if(draft)require(draft->prefix_rows()==(e->sealed_selection.draft.at("head_prefix")=="production"?91392u:80128u),"runtime prefix selected");
'''+t[end:];t=t.replace('{"qsa_attention","unknown"},{"other_fusion","unknown"}','{"qsa_attention","unknown"},{"head_prefix","unknown"}');f.write_text(t)
f=P/'build_engine.py';t=f.read_text().replace('300_000_000','150_000_000');f.write_text(t)
# Current packet103 composition including its packet101 geometry; no fusion overlay.
row=json.loads((T/'lineage/selection.json').read_text());row['choices'].pop('other_fusion')
(P/'lineage/selection.json').write_text(json.dumps(row,indent=2)+'\n')
for leaf in ['dispatch-speed6.json','memory-plan.json']:(P/'lineage'/leaf).write_bytes((BASE/leaf).read_bytes())
f=P/'bracket_config.py';t=f.read_text().replace("row['choices']['other_fusion']='production';", "row['draft']['head_prefix']='production';").replace("candidate['choices']['other_fusion']='fused'", "candidate['draft']['head_prefix']='p114-80128'").replace("only_changed_dimension='other_fusion'", "only_changed_dimension='draft.head_prefix'");f.write_text(t)
f=P/'bracket.py';t=f.read_text().replace("DOMAINS = {'other_fusion': ('production', 'fused')}", 'DOMAINS = {}').replace("require(view['draft'][key] == value, 'draft bytes/layout differ; reload required: ' + key)", "require(view['draft'][key] in ('production','p114-80128') if key=='head_prefix' else view['draft'][key] == value, 'draft bytes/layout differ; reload required: ' + key)");t=t.replace("        require(not view['choices']['miss']", "        require(view['draft']['head_format']=='production', 'prefix switch requires shared full head')\n        require(not view['choices']['miss']");f.write_text(t)
f=P/'protocol_gate.py';t=f.read_text().replace("row['choices'].pop('other_fusion')", "row['draft']['head_prefix']='production'");f.write_text(t)
f=P/'startup114.py';t=f.read_text().replace(";projection['choices']['other_fusion']='production'",'');t=t.replace("from kd_reference import command,TARGET_ONLY", "from kd_reference114 import command,TARGET_ONLY");f.write_text(t)
# Copy repaired KD reader, bounded only in its __main__, and the draft-reference helper.
for leaf in ['kd_projection_replay.py','kd_reference.py']:(P/leaf.replace('.py','114.py')).write_bytes((BASE/leaf).read_bytes())
f=P/'kd_reference114.py';t=f.read_text();start=t.index('    from bundle_selection');end=t.index('    result =',start);t=t[:start]+"    allowed=[json.loads((Path(__file__).resolve().parent/'lineage'/n).read_text()) for n in ('selection.json','candidate.json')]\n    assert target in allowed, 'unsealed packet114 KD view'\n"+t[end:];f.write_text(t)
f=P/'audit_sources.py';t=f.read_text().replace("('main.cpp','p49d_submit.cpp','argument_block.hpp')", "('p83_head.hpp','p59c_select.hpp')");f.write_text(t)
# Acceptance may change with a smaller prefix. Still demand identical repeat counts within each arm.
f=P/'compare.py';t=f.read_text().replace("    require(all(r['acceptance_counts']==rows[0]['acceptance_counts'] for r in rows), 'per-prompt acceptance changed across views')", "    for arm in ('control','candidate'):\n        group=[r for r in rows if r['choice']==arm]\n        require(all(r['acceptance_counts']==group[0]['acceptance_counts'] for r in group), 'acceptance changed within same arm')")
t=t.replace("    save(output / 'bracket-summary.json', result)", "    if proof['kind']=='bracket':\n        result['candidate_accepted']=drift<=3.0 and result['strict_candidate_control_ratio']>=1.005\n        result['decision']='accept' if result['candidate_accepted'] else 'reject'\n        result['preregistered_rows']=80128\n        result['retune_allowed']=False\n    save(output / 'bracket-summary.json', result)")
f.write_text(t)
# Operator fixture uses exact unchanged p33 row bodies and round2 argmax.
s=(P.parent/'packet56-draft-prefix/p56_cpu_gate.cpp').read_text().replace('n==p56::rows(full_vocab)&&n%256==0','(n==91392||n==80128)&&n%256==0').replace('{256u,32768u,65536u,98304u,sealed_n,full_vocab}','{sealed_n}');(P/'prefix_cpu.cpp').write_text(s)
# Docs must be replaced with this packet's account before sealing.
for leaf in ['README.md','CPU-PREPARATION-CLOSEOUT.md','DO-NOT-REPEAT.md','LAYOUT-AUDIT.md','RETENTION.md','PREREGISTRATION.md']:(P/leaf).write_text('# Packet114\n\nCPU preparation in progress; device quality and speed unmeasured.\n')
print('copied frozen packet103 sources and v5 wrapper; selection 80128')
