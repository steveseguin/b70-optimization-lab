"""Small CPU-only citation/receipt audit; writes only packet158 evidence."""
import datetime
import hashlib
import json
import re
import resource
import shutil
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
S = P.parent
ROOT = S.parents[2]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    assert shutil.disk_usage(P).free >= 27_000_000_000
    out = P/'evidence'
    out.mkdir(exist_ok=True)
    packets = ('66','79','101','105','105b','106','106b','108','114','120','122','126','129','146','156')
    dnrs = []
    for packet in packets:
        found = sorted(S.glob('packet'+packet+'-*/DO-NOT-REPEAT.md'))
        assert found, packet
        dnrs += found
    for packet in ('34','59','59c','107','112','157'):
        dnrs += sorted(S.glob('packet'+packet+'-*/DO-NOT-REPEAT.md'))
    matches = subprocess.run(['rg','-n','--no-heading',
        'draft|head|prefix|HC|attention|route|closed|Closed|repeat|geometry|arithmetic|state|CPU|byte|scale|kernel|placement|finite|scratch|source|load|status|reset|launch|tim|rank|packet|Packet',
        *map(str,dnrs)], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    (out/'dnr-matches.txt').write_text(matches.stdout.replace(str(ROOT)+'/', ''))
    source_names = ('mtp.hpp','mtp_kernels.cpp','p59_draft.hpp','p59_hc.hpp',
        'p59c_select.hpp','p33_submit.cpp','p33_candidates.hpp','specialised.hpp',
        'p49_qsa_submit.cpp','p49_qsa_kernel.hpp','adapter.cpp','route42.hpp',
        'round2.hpp','round2_submit.cpp','p42_submit.cpp','p42_tiny.hpp',
        'p28/dense.hpp','dispatch-speed6.json','selection.json','p56_prefix.hpp')
    files = dnrs + [S/'packet136-record-bundle'/n for n in source_names]
    files += [S/'packet157-draft-decomp/v5/native/split_timing.hpp',
              S/'packet157-draft-decomp/v5/analyze.py',
              S/'packet122-draft-budget/roofline.py',
              ROOT/'notes/2026-10-19-own-runtime-packet154-result.md',
              ROOT/'notes/2026-10-18-own-runtime-packet108-micro-result.md',
              ROOT/'notes/2026-10-18-own-runtime-packet106b-grid-result.md',
              ROOT/'notes/2026-10-18-own-runtime-packet120-grid-result.md',
              ROOT/'notes/2026-10-18-own-runtime-packet122-micro-result.md']
    audit = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        required_packets=list(packets), dnr_file_count=len(dnrs),
        files=[dict(path=str(f.relative_to(ROOT)),sha256=sha(f),lines=len(f.read_text().splitlines())) for f in files])
    (out/'source-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    summaries = sorted((S/'packet157-draft-decomp/v5/evidence').glob('device*/bracket-summary.json'))
    status = []
    for f in summaries:
        row=json.loads(f.read_text())
        status.append(dict(path=str(f.relative_to(ROOT)),sha256=sha(f),
                           passed=row.get('passed'),kind=row.get('kind')))
    failed = S/'packet157-draft-decomp/v5/evidence/device-p157-smoke-A/run/ranks/failure-before-teardown.json'
    poll = dict(utc=audit['utc'],summaries=status)
    if failed.exists():
        row=json.loads(failed.read_text())
        poll['first_smoke_failure']=dict(path=str(failed.relative_to(ROOT)),sha256=sha(failed),reason=row.get('reason'))
    (out/'packet157-status.json').write_text(json.dumps(poll,indent=2)+'\n')
    bad=[]
    for f in [*P.glob('*.md'),*P.glob('briefs/*.md')]:
        for target in re.findall(r'\]\(([^)]+)\)',f.read_text()):
            if '://' in target or target.startswith('#'):
                continue
            dest=(f.parent/target.split('#')[0]).resolve()
            if not dest.exists():
                bad.append([str(f.relative_to(P)),target])
    assert not bad, bad
    data=json.loads((P/'roofline.json').read_text())
    assert len(data['ranked'])==8 and data['ranked']==sorted(data['ranked'],key=lambda r:r['gap_ms'],reverse=True)
    for row in data['ranked']:
        assert abs(row['gap_ms']-(row['measured_ms']-row['useful_bytes']/537e6))<1e-12
    for f,h in data['sources'].items():
        assert sha(ROOT/f)==h, f
    checks=dict(passed=True,device_executed=False,model_payload_read=False,
        dnr_files=len(dnrs),source_files=len(files),eight_groups=True,
        arithmetic_and_source_hashes=True,markdown_links=True,
        prepared_briefs=[f.name for f in sorted((P/'briefs').glob('*.md'))],
        note='Documentation/source accounting only; no compiled byte or device qualification claimed.')
    (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(checks))


if __name__=='__main__':
    main()
