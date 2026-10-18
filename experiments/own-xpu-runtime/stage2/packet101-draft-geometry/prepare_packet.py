"""Seal four named views after draft repeat and complete startup gates."""
import importlib.util,json,os
from build_engine import P,ROOT,BASE,sha,save,limits,provenance,check_map
from bundle_selection import aliases,views,selection,name
from memory_plans import plan
def main():
    limits();build=provenance();sources=dict(build['sources'])
    reports={leaf:json.loads((P/'evidence'/leaf).read_text()) for leaf in ('source-audit.json','cpu-gates.json','full-shape.json','startup-refusals.json')}
    for leaf,report in reports.items():
        assert report['passed'] and report['device_executed'] is False
        check_map(ROOT,report['sources']);sources.update(report['sources'])
        sources[str((P/'evidence'/leaf).relative_to(ROOT))]=sha(P/'evidence'/leaf)
    shape=reports['full-shape.json']
    assert {(r['view'],r['rank']) for r in shape['runs']}=={(n,r) for n in views() for r in (0,1)}
    for row in shape['runs']:
        assert row['passed'] and row['selection_key_consumers_verified'] and row['expanded_head_stride']==3380
        for artifact in row['artifacts'].values():sources[artifact['path']]=artifact['sha256']
    gates=reports['cpu-gates.json']['runs']
    for kind in ('qsa','hc'):
        selected=[r for r in gates if r['kind']==kind]
        assert {(r['compiler'],r['repeat']) for r in selected}=={(c,r) for c in ('GNU','Intel') for r in (1,2)}
        assert len({r['raw_sha256'] for r in selected})==1
    check_map(ROOT,sources)
    sources.update(json.loads((P/'dependency-pins.json').read_text()))
    for f in [*P.glob('*.py'),P/'copy-lineage.json',P/'placement-policy.json',P/'shared-wrapper-pin.json',P/'selection-template.json',P/'build-device-receipt.json',BASE/'bundle_selection.py',BASE/'selection-template.json']:
        sources[str(f.relative_to(ROOT))]=sha(f)
    from bootstrap import install
    install()
    spec=importlib.util.spec_from_file_location('p101_generic_seal',P.parent/'screen/seal.py')
    generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
    qsa=next(r for r in gates if r['kind']=='qsa' and r['compiler']=='GNU' and r['repeat']==1)
    for label,v in aliases().items():
        view=P/'selections'/label;view.mkdir(parents=True,exist_ok=True)
        assert not (view/'screen-seal.json').exists(),'sealed views are immutable'
        save(view/'selection.json',selection(v));save(view/'memory-plan.json',plan(v))
        (view/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
        artifacts={}
        for mode in ('device','gnu-host'):
            dest=view/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():os.link(P/'build'/mode/'own-rt-iq3',dest)
            artifacts[str(dest.relative_to(view))]=sha(dest)
        audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,
                   target_layers=[24,24],draft_prefix_rows=91392,rank0_private_prefix_bytes=0,
                   target_head=v[8],rank1_separate_expanded_prefix_bytes=91392*3380 if v[8]!='production' else 0,
                   dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=artifacts['build/device/own-rt-iq3'],
                   engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p56_config.hpp','p56_prefix.hpp')},
                   memory_sources=shape['sources'],startup_view=name(*v))
        save(view/'placement-audit.json',audit)
        bound=dict(sources);bound[str((view/'placement-audit.json').relative_to(ROOT))]=sha(view/'placement-audit.json')
        for leaf in ('expected','actual'):(view/('fixture-'+leaf+'.bin.gz')).write_bytes((ROOT/qsa['fixture']).read_bytes())
        bp=view/'build-receipt.json';fp=view/'byte-fixture.json'
        save(bp,dict(passed=True,device_executed=False,sources=bound,artifacts=artifacts))
        save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
            build_receipt_sha256=sha(bp),sources=reports['cpu-gates.json']['sources'],
            changed_class='Existing draft split32: deterministic reference-exact arithmetic in GNU/Intel twice. HC is identical to packet97. Target runtime/binary unchanged; old-draft parity not asserted.',
            command=['python3','-B',str(P/'cpu_gate.py')],
            **{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(view/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
        generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
        print(label,'sealed',flush=True)
if __name__=='__main__':main()
