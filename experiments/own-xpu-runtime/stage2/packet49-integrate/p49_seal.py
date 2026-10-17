"""Packet49 scoped CPU/build seal. Completion of the oracle never reseals it."""
import argparse, json
from pathlib import Path
import build
from storage import digest
from seal_context import precise
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
GATES=('p49-cpu-gates.json','p49-plan-gates.json','p49-snapshot-gates.json','p49-python-gates.json','p49-asan-gates.json','p49-asan-snapshot-gates.json')
def checked():
    current=build.compiled_sources();artifacts={};modes={}
    for mode in ('gnu-host','device','asan'):
        path=P/f'build-{mode}-receipt.json';row=json.loads(path.read_text())
        assert row['passed'] and row['device_executed'] is False and row['mode']==mode
        assert row['compiled_sources_sha256']==current,'stale '+mode+' build'
        assert row.get('checked_mirror_sha256'),'missing actual compiler input binding'
        for name,sha in row['checked_mirror_sha256'].items():assert digest(B/name)==sha,'compiler mirror changed'
        assert row['compile_commands_sha256']==digest(B/mode/'compile_commands.json')
        for command in json.loads((B/mode/'compile_commands.json').read_text()):
            precise(command.get('arguments',command.get('command')),mode=='device')
        for name,sha in row['link_files_sha256'].items():
            assert digest(B/name)==sha;precise((B/name).read_text(),mode=='device')
        for name,sha in row['artifacts_sha256'].items():
            assert digest(B/name)==sha;artifacts[name]=sha
        for name in ('own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures','p49-qsa-fixtures'):
            assert mode+'/'+name in artifacts
        modes[mode]=digest(path)
    gates={name:json.loads((P/name).read_text()) for name in GATES}
    for name,row in gates.items():assert row['passed'] and row.get('device_executed',False) is False,name
    cpu=gates['p49-cpu-gates.json'];assert cpu['compiled_sources_sha256']==current
    assert len(cpu['fixtures'])==6 and len(cpu['owner_suites'])==6
    for row in cpu['owner_suites']:
        assert row['passed'] and row['binary_sha256']==artifacts['gnu-host/'+row['name']]
    outputs={}
    for row in cpu['fixtures']:
        assert row['binary_sha256']==artifacts['gnu-host/'+row['name']]
        assert row['receipt']['output_sha256']==row['output_sha256']==digest(Path(row['output'])/'output.bin')
        from p49_cpu_gate import summarize_receipt
        assert row['native_receipt_sha256']==digest(Path(row['output'])/'receipt.json')
        assert row['receipt']==summarize_receipt(json.loads((Path(row['output'])/'receipt.json').read_text()))
        outputs.setdefault(row['name'],[]).append(row['output_sha256'])
    assert all(len(v)==2 and len(set(v))==1 for v in outputs.values())
    plan=gates['p49-plan-gates.json'];assert plan['plan_dispatch_rows']==12 and plan['weight_bytes_read']==0
    assert plan['binary_sha256']==digest(B/'p49-plan/after')
    assert plan['generated_sha256']==digest(B/'p49-plan/after.cpp')
    assert plan['writer_sites']['sha256']==digest(P/plan['writer_sites']['path'])
    for name,sha in plan['sources_sha256'].items():assert digest(P/name)==sha
    for mode,name in (('gnu-host','p49-snapshot-gates.json'),('asan','p49-asan-snapshot-gates.json')):
        snapshot=gates[name];assert snapshot['build']['binary_sha256']==artifacts[mode+'/own-rt-iq3']
        assert snapshot['cases']==31 and snapshot['gate_count']==26
        if mode=='asan':assert snapshot['sanitizer_options']=={'ASAN_OPTIONS':'halt_on_error=1:detect_leaks=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
        for name,sha in snapshot['source_sha256'].items():assert digest(P/name)==sha
    for row in gates['p49-asan-gates.json']['rows']:
        assert row['binary_sha256']==artifacts['asan/p49-qsa-fixtures']
        assert row['receipt']['checks']==88 and row['receipt']['reference_exact']
        assert row['output_sha256']==outputs['p49-qsa-fixtures'][0]
        assert digest(Path(row['output'])/'output.bin')==row['output_sha256']
        assert digest(Path(row['output'])/'receipt.json')==row['native_receipt_sha256']
        assert row['receipt']==summarize_receipt(json.loads((Path(row['output'])/'receipt.json').read_text()))
    assert len(gates['p49-asan-gates.json']['rows'])==2
    assert gates['p49-python-gates.json']['tests']>0 and gates['p49-python-gates.json']['failures']==gates['p49-python-gates.json']['errors']==0
    for name,sha in gates['p49-python-gates.json']['sources_sha256'].items():assert digest(P/name)==sha
    sources=build.sources()
    for name in ('coordinator_windows.sh','dispatch-speed6.json','dispatch-speed6-provenance.json'):
        sources[str((P/name).relative_to(ROOT))]=digest(P/name)
    from oracle.oracle_job import source_bindings
    oracle_build=source_bindings()
    oracle_inputs={name:digest(P/'oracle'/name) for name in ('arithmetic.json','build-receipt.json','cpu-proof.json')}
    oracle_proof=json.loads((P/'oracle/cpu-proof.json').read_text())
    assert oracle_proof['passed'] and oracle_proof['device_executed'] is False
    for file in (P/'oracle').rglob('*'):
        if file.is_file() and file.suffix in ('.py','.hpp','.cpp') and 'results' not in file.parts and 'build' not in file.parts:
            sources[str(file.relative_to(ROOT))]=digest(file)
    return dict(schema='packet49.scoped-cpu-seal.v1',passed=True,device_executed=False,
        arithmetic='iq3-p49-split32-v1',parent_commit='34c62b433',sources=sources,
        artifacts_sha256=artifacts,mode_receipts_sha256=modes,
        oracle_inputs_sha256=oracle_inputs,oracle_binary_sha256=oracle_build['binary_sha256'],
        gates_sha256={name:digest(P/name) for name in GATES},
        official_manifest_sha256=digest(P/'mtp-manifest.tsv'),memory_plan=json.loads((P/'memory-plan.json').read_text()),
        input_sha256=digest(B/'input/input.json'),
        p33_linked_fixture_host_sha256=outputs['p33-linked-fixtures'][0],
        p49_qsa_fixture_host_sha256=outputs['p49-qsa-fixtures'][0],
        nongemv_fixture_host_sha256_by_context={'4096':outputs['nongemv-fixtures'][0]},
        scope=dict(context=4096,draft_rank=1,target_split=23,first_card=0,
            host_compilers=['GNU','GNU ASAN/UBSAN'],device_execution_pending=True,full_model_oracle_pending=True,
            full_model_qualification='Coordinator windows against independent completed oracle required',
            p48_integrated=False,p48_reason='Matched production decision pending packet48b'))
def verify():
    row=json.loads((P/'build-receipt.json').read_text())
    assert row==checked(),'packet49 seal differs from current evidence'
    return row
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');a=parser.parse_args()
    row=verify() if a.verify else checked()
    if not a.verify:(P/'build-receipt.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(dict(passed=True,device_executed=False,artifacts=len(row['artifacts_sha256']),sources=len(row['sources']))))
if __name__=='__main__':main()
