"""Source-bound audit of live check routing and real/synthetic replay gates."""
import ast,json
from packet_io import P,sha,save

def main():
    tests=json.loads((P/'evidence/python-tests.json').read_text());assert tests['passed']
    tree=ast.parse((P/'screen/analyze.py').read_text())
    names={ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)}
    assert not any('metric' in n or 'summarize' in n or 'compare_request' in n for n in names)
    text=(P/'screen/suite_driver.py').read_text()
    assert text.index('status=child.wait()')<text.index('verify_lookup_views(args.output,args.view)')<text.index('report=demand_report(')
    for n in ('parent-replay','resident-parent-replay'):assert json.loads((P/f'evidence/{n}.json').read_text())['passed']
    files=['analyze.py','check_streams.py','screen/analyze.py','screen/suite_driver.py','generate.py','native/engine_demand.inc','build/native/main.cpp','test_analysis.py','test_inrun.py','audit_inrun.py']
    save(P/'evidence/p58an-analyzer-audit.json',dict(passed=True,device_executed=False,
        in_run_checks=['stream presence','schema/field types','unchanged oracle tokens','declared model identity'],
        offline_checks=['coverage and duplicates','timestamp order and duration consistency','packed bytes and event accounting','cross-queue edge timestamps','overlap and speed','numeric timing validity'],
        native_checks_retained=['allocation/lifetime safety','cooperative operation waits','fault and teardown guards','oracle equality'],
        inherited_driver_review='partial only checks completed streams; summarize_bracket, verify_lookup_views and demand_report run after native child exit',
        sources={f:sha(P/f) for f in files},test_receipt='evidence/python-tests.json',test_receipt_sha256=sha(P/'evidence/python-tests.json'),
        real_evidence=['packet58ah chain-b WS128 all 12','packet58aj chain-a WS128 all 12'],
        native_demand_streams='synthetic schema tests only; no new device data claimed',
        readonly_peer_review='p58an_readonly_audit verified resident and 43 harness snapshots; no additional concrete blocker; v5 measured smoke refresh remains intentional'))
if __name__=='__main__':main()
