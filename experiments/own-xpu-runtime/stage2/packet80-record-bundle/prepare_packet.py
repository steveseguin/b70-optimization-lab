"""Seal all CPU-checked compositions/placements; never start a device."""
import gzip,importlib.util,json,os
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import PLACEMENTS,views,choices
from chain_seal import check_map

def main():
    limits()
    from stopped_archive import require_fresh_chain
    require_fresh_chain(B)
    from bootstrap import install
    install()
    names=('cpu-byte-identity.json','retirement-byte-identity.json','protocol.json','full-shape.json','memory-admission.json','cpu-gates.json')
    reports={n:json.loads((P/'evidence'/n).read_text()) for n in names}
    build=json.loads((P/'build-device-receipt.json').read_text())
    for r in (build,*reports.values()):
        assert r['passed'] and r['device_executed'] is False
        check_map(ROOT,r['sources'])
    check_map(P,build['artifacts'])
    assert len(reports['full-shape.json']['runs'])==len(views())*len(PLACEMENTS)*2
    assert len(reports['cpu-gates.json']['rows'])==1+len(views())*len(PLACEMENTS)*2
    assert reports['cpu-gates.json']['build_receipt_sha256']==sha(P/'build-device-receipt.json')
    assert set(reports['cpu-byte-identity.json']['views'])==set(views())
    sources=dict(build['sources'])
    for r in reports.values():sources.update(r['sources'])
    sources.update(json.loads((P/'dependency-pins.json').read_text()))
    extras=[*P.glob('*.py'),P/'placement-policy.json',P/'dependency-pins.json',P/'selection-template.json',P/'shared-wrapper-pin.json',*[P/'evidence'/n for n in names]]
    sources.update({str(f.relative_to(ROOT)):sha(f) for f in extras})
    spec=importlib.util.spec_from_file_location('packet80_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
    for name,v in views().items():
        selected=reports['cpu-byte-identity.json']['views'][name]
        assert selected['passed'] and selected['choices']==choices(*v)
        assert {(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)}
        assert len({r['candidate_sha256'] for r in selected['runs']})==1
        for run in selected['runs']:
            assert run['cases']==2096 and run['expected_sha256']==run['candidate_sha256']
            for kind in ('expected','candidate'):
                path=ROOT/run['path']/(kind+'.bin.gz')
                assert __import__('hashlib').sha256(gzip.decompress(path.read_bytes())).hexdigest()==run[kind+'_sha256']
        # Content-addressed exact fixture; all views may share identical bytes.
        raw=(ROOT/selected['runs'][0]['path']/'candidate.bin.gz').read_bytes()
        fixture=P/'evidence'/('operator-bytes-'+selected['runs'][0]['candidate_sha256']+'.bin.gz')
        if not fixture.exists():fixture.write_bytes(raw)
        assert fixture.read_bytes()==raw
        for placement,(rank,split,boundary) in PLACEMENTS.items():
            view=P/'selections'/(name+'--placement-'+placement);view.mkdir(parents=True,exist_ok=True)
            assert not (view/'screen-seal.json').exists(),'sealed view exists; use fast_reseal for selection'
            s=json.loads((P/'selection-template.json').read_text());s['choices']=choices(*v);save(view/'selection.json',s)
            for n in ('dispatch-speed6.json','memory-plan.json'):(view/n).write_bytes((P/n).read_bytes())
            for n in ('device','gnu-host'):
                dest=view/'build'/n/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():os.link(B/n/'own-rt-iq3',dest)
                assert sha(dest)==build['artifacts']['build/'+n+'/own-rt-iq3']
            for n in ('expected','actual'):
                dest=view/('fixture-'+n+'.bin.gz')
                if not dest.exists():os.link(fixture,dest)
            audit=dict(placement=placement,draft_rank=rank,target_split=split,layer_boundary=boundary,target_layers=[boundary,48-boundary],
                draft_prefix_rows=91392,rank0_private_prefix_bytes=308904960 if rank==0 else 0,
                dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=sha(view/'build/device/own-rt-iq3'),
                engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p56_config.hpp','p56_prefix.hpp')},
                memory_sources=reports['memory-admission.json']['sources'])
            save(view/'placement-audit.json',audit)
            src={**sources,str((view/'placement-audit.json').relative_to(ROOT)):sha(view/'placement-audit.json')}
            bp=view/'build-receipt.json';fp=view/'byte-fixture.json'
            save(bp,dict(passed=True,device_executed=False,sources=src,artifacts=build['artifacts']))
            save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(bp),sources=reports['cpu-byte-identity.json']['sources'],
                changed_class='Combined selected operators: exact complete output/scratch bytes under GNU/Intel, two repeats; full startup, memory census, native miniature target/draft and reverse handoff separately bound.',
                command=['python3','-B',str(P/'cpu_gate.py')],
                **{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(view/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
            generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
    save(P/'cpu-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,
        files={str(f.relative_to(ROOT)):sha(f) for f in extras}))
    print('64 composed placement views sealed; no device execution')
if __name__=='__main__':main()
