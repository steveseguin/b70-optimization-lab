"""ROOT RELEASE ONLY, after archive: compact depth2 evidence, no source cleanup."""
from pathlib import Path
import argparse,gzip,hashlib,json
from common import CANDIDATE,finished,read,sha
parser=argparse.ArgumentParser();parser.add_argument('--cross-depth-proof',type=Path,required=True);a=parser.parse_args()
root=CANDIDATE;checks=finished(root);archive=read(root/'state-archive.json');assert archive['removal_completed']and archive['removed_files_absent']
proof=read(a.cross_depth_proof);assert type(proof.get('passed'))is bool
here=Path(__file__).resolve().parent;out=here/'depth2-aba64k-r1-evidence';out.mkdir(exist_ok=False);files=[]
def retain(p,rel):
 data=p.read_bytes();dest=out/(rel+'.gz');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(gzip.compress(data,mtime=0));digest=hashlib.sha256(data).hexdigest();assert hashlib.sha256(gzip.decompress(dest.read_bytes())).hexdigest()==digest
 files.append(dict(source=str(p),retained=str(dest.relative_to(out)),bytes=len(data),sha256=digest,retained_sha256=sha(dest)))
for p in sorted(root.rglob('*')):
 if p.is_file()and p.suffix in ['.json','.jsonl','.tsv','.txt','.log','.i32','.stdout','.stderr']:retain(p,'run/'+str(p.relative_to(root)))
plan=read(root/'plan.json');pins=[]
for name,expected in plan['pins'].items():
 p=Path(name);assert sha(p)==expected
 pins.append(dict(path=name,bytes=p.stat().st_size,sha256=expected))
 if p.name!='sc117-engine'and not p.is_relative_to(root):retain(p,'pinned-sources/'+str(p).lstrip('/'))
retain(a.cross_depth_proof,'cross-depth-proof.json')
for n in ['archive_depth2.py','retain_depth2.py','compare_first_a.py','common.py','restore_first_a.py']:retain(here/n,'helpers/'+n)
summary=dict(schema='ownrt.depth2-aba64k-retained.v1',finished=checks,cross_depth_proof_passed=proof['passed'],cross_depth_proof_phase=proof.get('stage'),cross_depth_error=proof.get('error'),scope='Depth2 A/B/A64K reset plus exact crossdepth outcome; any source/layout difference remains a failure, no proof weakening. Not12-suite speed. Metadata and transport maps remain.',archive=archive,source_pins=pins)
(out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');(out/'index.json').write_text(json.dumps(dict(schema='ownrt.depth2-aba64k-retention-index.v1',summary='summary.json',summary_sha256=sha(out/'summary.json'),files=files),indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(evidence=str(out/'index.json'),retained_files=len(files),compressed_bytes=sum((out/x['retained']).stat().st_size for x in files))))
