"""End-to-end report test using explicitly relabeled historical CPU fixtures.

No fixture-derived costs are published as packet77 measurements. Only pass/fail,
row coverage and input provenance are retained; all synthetic receipts are temp.
"""
import json
import os
from pathlib import Path
import tempfile

from build_engine import P, ROOT, sha, save, limits
from report import generate, markdown


def main():
    limits()
    historical=P.parent/'packet69-rank1-head/screen/attr/evidence/p69-attribution-B-a/run'
    binary=json.loads((P/'build-device-receipt.json').read_text())['artifacts']['build/device/own-rt-iq3']
    sources={}
    with tempfile.TemporaryDirectory(prefix='packet77-report-fixture-') as tmp:
        root=Path(tmp)
        for arm in ('control','attribution'):
            for receipt in sorted((historical/arm).glob('*/receipt.json')):
                dest=root/arm/receipt.parent.name;dest.mkdir(parents=True)
                row=json.loads(receipt.read_text())
                # Test-only identity normalization; original receipts are untouched.
                # generate() must still reject the original historical identity.
                row.update(binary_sha256=binary,selection_sha256=sha(P/'selection.json'))
                (dest/'receipt.json').write_text(json.dumps(row))
                sources[str(receipt.relative_to(ROOT))]=sha(receipt)
                for rank in (0,1):
                    target=dest/f'rank{rank}';target.mkdir()
                    for name in ('sites.jsonl','timings.jsonl'):
                        source=receipt.parent/f'rank{rank}'/name
                        os.link(source,target/name)
                        sources[str(source.relative_to(ROOT))]=sha(source)
        result=generate(root)
        rendered=markdown(result)
        assert result['passed'] and not result['submission_eligible']
        assert {r['rank'] for r in result['lever_ranking']}=={0,1}
        assert all(any(r['rank']==rank and r['site']==site for r in result['lever_ranking'])
                   for rank in (0,1) for site in ('expsgate','expsdown','hc.a.gate','hc.f.gate','gdn.recurrence','route'))
        assert len(result['rank1_outside_split'])==5
        assert 'Instrumentation overhead' in rendered
        receipt=next((root/'control').glob('*/receipt.json'))
        row=json.loads(receipt.read_text());row['binary_sha256']='different';receipt.write_text(json.dumps(row))
        try:generate(root)
        except ValueError:pass
        else:raise AssertionError('changed binary identity accepted')
        counts=dict(site_rows=len(result['sites']),lever_rows=len(result['lever_ranking']),
                    outside_parts=len(result['rank1_outside_split']))
    save(P/'evidence/report-fixture.json',dict(passed=True,device_executed=False,
        scope='report software test only; historical packet69 data with temporary synthetic identity normalization; no packet77 measurements',
        fixture_sources=sources,counts=counts,identity_mismatch_refused=True,
        source_sha256=sha(P/'report_fixture_gate.py')))
    print('historical-fixture report + table rendering PASS; no packet77 costs retained')


if __name__=='__main__':main()
