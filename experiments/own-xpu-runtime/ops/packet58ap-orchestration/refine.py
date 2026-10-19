"""Close inherited packaging references and retain exact parent proof bytes."""
import json,shutil
from prepare import P,O,ROOT,AM,AJ,sha,save,copy
def main():
    for name in ('k1_cpu_gate.py','fullshape_submit_gate.py','postload_allocation_gate.py','startup_gate.py','literal_audit.py','plan_queue.py','restore-inputs.json'):
        (P/name).unlink()
    for name in ('58ag-fullshape-submit-cpu.json','58ag-postload-allocation-cpu.json','58ag-k1-async-cpu.json'):
        copy(AJ/'lineage'/name,P/'lineage'/name)
    parent=json.loads((P/'parent-binding.json').read_text())
    for name in ('bytes','ownership','resident-cpu'):
        src=AM/f'evidence/{name}.json';dest=P/f'lineage/packet58am/evidence/{name}.json';copy(src,dest)
        assert json.loads(dest.read_text())['passed'] is True
        parent['sources'][str(dest.relative_to(P))]=sha(dest)
    save(P/'parent-binding.json',parent)
    f=P/'test_suite_driver58.py';t=f.read_text().replace("'check_wait(dev(c).wait(e, std::chrono::seconds(a.wait_seconds))'","'require(dev(c).wait(e, std::chrono::seconds(a.wait_seconds))'").replace("'check_wait(std::chrono::steady_clock::now()<end'","'require(std::chrono::steady_clock::now()<end'").replace("'wait-timeout.json'","'a.wait_seconds>=300 && a.wait_seconds<=3600'");f.write_text(t)
    f=P/'packet58_submission.py';t=f.read_text().replace('lab.packet58aj.realistic-suite-result.v1','lab.packet58ap.realistic-suite-result.v1').replace('packet58aj-chain-a-realistic','packet58ap-chain-a-realistic').replace('packet58aj-resident-tile16','packet58ap-demand-resident-tile16').replace('# Packet58aj one-card scoped measurement','# Packet58ap one-card scoped measurement')
    t=t.replace("    check_lookups(e.read(name + '/run/run/receipt.json'))", "    check_lookups(e.read(name + '/run/run/receipt.json'))\n    require(native.get('demand_variant')=='bcs-demand-retained32x2' and native.get('demand_identity')=='packet58ap-chain-a', 'native demand composition differs')")
    f.write_text(t)
    f=P/'test_submission.py';t=f.read_text().replace("native['lookup_residency']=", "native.update(demand_variant='bcs-demand-retained32x2',demand_identity='packet58ap-chain-a')\n            native['lookup_residency']=");f.write_text(t)
    # File source closures and restoration paths refer to these immutable archives,
    # not a future state of the parent packet.
    save(P/'lineage/provenance.json',dict(template=str(AJ.relative_to(ROOT)),candidate=str(AM.relative_to(ROOT)),candidate_build_sha256=parent['build_sha256'],candidate_artifacts=parent['artifacts'],candidate_recompiled=False,k1_adapter_only_recompiled=True))
if __name__=='__main__':main()
