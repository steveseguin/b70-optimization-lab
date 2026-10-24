"""Fixed18 closed archive aliases using unchanged verified container machinery."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
PARENT=P.parent/'canonical-archives/consolidate.py'
PARENT_SHA='64b4c0131eeb8ea0f87bb8fea29864b79dc0b6e9ffc4fb2a7be1e6e1e726ee33'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
need(sha(PARENT)==PARENT_SHA,'frozen verified container machinery')
s=importlib.util.spec_from_file_location('closed_bundle_container_parent',PARENT);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
M.P=P;M.__file__=__file__;M.APPRAISAL=P/'appraisal.json'
M.APPRAISAL_SHA='43a96df71ac71e5ea217d73cd3117896d5a12274388859e6c6cf75a3e044c128'
M.DEST=Path('/home/steve/own-xpu-runtime-results/gsq-closed-bundle-canonical-a')
def index(path):
 with gzip.open(path,'rt') as f:rows=[json.loads(line) for line in f]
 return {x['path']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in rows if x['root']=='evidence' and x['path'].endswith('/state.bundle')}
def authority(batch):
 need(type(batch)is int and 0<=batch<18,'fixed18 archives');need(sha(M.APPRAISAL)==M.APPRAISAL_SHA,'fixed full mapping')
 a=json.loads(M.APPRAISAL.read_text());need(len(a['mapping'])==18 and a['total_candidate_recovery_bytes']==532980776,'fixed18 recoverable extent')
 for f,h in a['authority_sha256'].items():
  p=R/f;need(sha(p)==h,'closed authority drift')
  if p.name=='review.json':
   r=json.loads(p.read_text());need(r['passed'] and r['physical_drain'] and r['kernel_fault_baseline_unchanged'],'closed audited owner')
 row=a['mapping'][batch];need(row['batch']==batch,'mapping order');original=Path(row['original_archive']);target=Path(row['canonical_archive'])
 need(original.parent==target.parent==M.USB and original!=target,'fixed distinct USB archives')
 need(original.name.startswith(('gsq-closed-state-bundle-','gsq-attribution-state-bundle-')) and target.name.startswith('gsq-expert-block-state-bundle-'),'release and retained canonical families')
 name=row['member'];expected={name:index(R/row['original_index'])[name]};base={name:index(R/row['canonical_index'])[name]}
 need(expected==base=={name:dict(bytes=row['member_bytes'],sha256=row['member_sha256'])},'full single-member equality')
 source=json.loads((R/row['source_complete']).read_text());need(source['passed'],'original completed archival')
 source_row=next(x for x in source['rows'] if x['batch']==row['source_batch'])
 canonical=json.loads((L/'storage/expert-block-closed/evidence/complete.json').read_text());need(canonical['passed'] and canonical['all_four_phases_passed'],'canonical complete archival')
 canonical_row=next(x for x in canonical['batches'] if x['name']==name)
 for prefix,entry in [('original',source_row),('canonical',canonical_row)]:
  need((row[prefix+'_archive'],row[prefix+'_archive_bytes'],row[prefix+'_archive_sha256'])==(entry['usb'],entry['archive_bytes'],entry['archive_sha256']),'completed archive inventory binding')
 return row,expected,base
M.authority=authority
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--verify',action='store_true');g.add_argument('--release-verified',action='store_true');p.add_argument('--batch',type=int,required=True);a=p.parse_args()
 print(json.dumps(M.verify(a.batch) if a.verify else M.release(a.batch)))
