#!/usr/bin/env python3
"""Four fixed prompt01 raw bundles; canonical verification and separate release."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,stat
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
PARENT=P.parent/'canonical-archives/consolidate.py';PARENT_SHA='64b4c0131eeb8ea0f87bb8fea29864b79dc0b6e9ffc4fb2a7be1e6e1e726ee33'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
need(sha(PARENT)==PARENT_SHA,'frozen canonical primitives')
s=importlib.util.spec_from_file_location('dense_raw_canonical_private',PARENT);C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
C.DEST=Path('/home/steve/own-xpu-runtime-results/gsq-dense-prompt01-canonical-a')
RAW=C.USB/'gsq-dense-q6-p33-engine-a'
APPRAISAL=P.parent/'raw-bundle-canonical-appraisal.json';APPRAISAL_SHA='c717e40639eacfae39913fbb4c7b63ab47657d8407092e13871c1b39fb28f2aa'
BINDING=P/'closure-binding.json';BINDING_SHA='4dba1ed22b7c084540fdf8c692dd6a7cec0ba648cdd0260565bf8c08d37ec639'
NAMES=tuple(f'prompt-01-{mode}/rank{rank}/state-2147483647/state.bundle' for mode in ('none','mtp') for rank in (0,1))
def mapping():
 need(sha(APPRAISAL)==APPRAISAL_SHA,'fixed four-bundle appraisal');a=json.loads(APPRAISAL.read_text())
 for f,h in a['authority_sha256'].items():need(sha(R/f)==h,'prior canonical authority')
 rows={x['relative_path']:x for x in a['potential_rows'] if x['relative_path'] in NAMES}
 need(set(rows)==set(NAMES) and sum(x['bytes'] for x in rows.values())==443486336,'only four fixed bundles')
 return rows
def authority(batch):
 need(type(batch)is int and 0<=batch<4,'fixed batch0..3')
 need(BINDING_SHA is not None and sha(BINDING)==BINDING_SHA,'actual Q6 closure binding pending')
 b=json.loads(BINDING.read_text());need(b['passed'] is True and b['released_paths']==list(NAMES),'explicit four-path release')
 for key in ('review','index','terminal'):
  need(sha(R/b[key]['path'])==b[key]['sha256'],'actual '+key+' identity')
 review=json.loads((R/b['review']['path']).read_text());term=json.loads((R/b['terminal']['path']).read_text())
 need(review['passed'] and review['all12_exact'] and review['bundles']==54 and review['measured_arms']==24 and review['physical_drain'] and review['kernel_fault_baseline_unchanged'] and review['native_binary_sha256']=='a0f9ffc58de704a276b237cbeec2b338ee873c0872bcae2da2214286aa5cce50','complete exact Q6 audit')
 need(review['index_sha256']==b['index']['sha256'] and review['full_result_sha256']==term['result']['full_result_sha256'] and review['plan_sha256']==term['plan_sha256'],'actual audit terminal joins')
 need(term['passed'] and term['children_exited'] and term['target_descriptors_empty'] and term['observed_target_contact']==[True,True] and term['first_error'] is None and term['original_error'] is None,'closed physical owner proof')
 found={}
 with gzip.open(R/b['index']['path'],'rt') as f:
  for line in f:
   need(len(line)<=16384,'bounded index row');x=json.loads(line)
   if x['root']=='evidence' and x['path'] in NAMES:
    need(x['path'] not in found,'unique audited raw bundle');found[x['path']]=x
 rows=mapping();need(set(found)==set(NAMES),'four actual audited payloads')
 for name in NAMES:need(found[name]['bytes']==rows[name]['bytes'] and found[name]['sha256']==rows[name]['raw_sha256'],'exact raw/canonical physical bytes')
 return rows[NAMES[batch]]
def review_pin():
 p=P/'evidence/independent-review.json';j=json.loads(p.read_text());need(j['passed'] and j['source_sha256'],'independent fixed adapter review')
 for f,h in j['source_sha256'].items():need(sha(R/f)==h,'reviewed source drift')
 return sha(p)
def raw_held(path,size):
 need(path in {RAW/n for n in NAMES} and path.resolve()==path and C.USB.resolve()==C.USB and C.USB.stat().st_dev==C.USB_DEVICE,'fixed canonical raw path/device')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_dev==C.USB_DEVICE and st.st_size==size,'raw inode/extent/device');return fd,C.identity(st),dict(mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,atime_ns=st.st_atime_ns)
 except BaseException:os.close(fd);raise
def descriptors(row):
 raw=RAW/row['relative_path'];fd,stamp,metadata=raw_held(raw,row['bytes']);out=[(fd,raw,stamp)]
 try:
  target=Path(row['canonical_archive']);fd,stamp=C.held(target,row['canonical_archive_bytes']);out.append((fd,target,stamp));need(out[0][2][:2]!=out[1][2][:2],'distinct raw and canonical inode');return out,metadata
 except BaseException:
  for fd,_,_ in out:os.close(fd)
  raise
def hashes(ds,row):
 C.compressed(*ds[0],row['raw_sha256']);C.compressed(*ds[1],row['canonical_archive_sha256'])
def verify(batch):
 C.limits();review=review_pin();row=authority(batch);C.anchor();d=C.DEST/f'batch-{batch:02d}';d.mkdir(mode=0o700);C.syncdir(C.DEST)
 result=dict(passed=False,phase='verify',batch=batch,row=row,helper_sha256=sha(__file__),binding_sha256=BINDING_SHA,review_sha256=review,released=False);ds=[]
 try:
  ds,metadata=descriptors(row);hashes(ds,row)
  expected={row['relative_path']:dict(bytes=row['bytes'],sha256=row['raw_sha256'])};members=C.members(*ds[1],expected)
  redirect=dict(schema='gsq.raw-bundle.restore.v1',row=row,original_path=str(ds[0][1]),raw_identity=ds[0][2],raw_metadata=metadata,canonical_identity=ds[1][2],canonical_member=members[row['relative_path']],restore='Verify canonical compressed SHA; extract only this exact member and verify raw length/SHA, then restore raw mode/uid/gid/mtime where supported. Original inode/ctime are historical identity, not recreatable. Keep all sibling state JSON/index/seal and old receipts.')
  C.save(d/'restore.json',redirect)
  for fd,path,st in ds:C.unchanged(fd,path,st)
  result.update(passed=True,raw_identity=ds[0][2],canonical_identity=ds[1][2],restore_sha256=sha(d/'restore.json'))
 except BaseException as e:result['error']=repr(e);raise
 finally:
  for fd,_,_ in ds:os.close(fd)
  C.save(d/'verified.json',result)
 return result
def release(batch):
 C.limits();review=review_pin();row=authority(batch);C.anchor();d=C.DEST/f'batch-{batch:02d}'
 need(d.resolve()==d and d.is_dir() and not os.path.lexists(d/'release-start.json') and not os.path.lexists(d/'released.json'),'fresh separate release')
 v=json.loads((d/'verified.json').read_text());need(v['passed'] and v['phase']=='verify' and v['batch']==batch and v['row']==row and v['helper_sha256']==sha(__file__) and v['binding_sha256']==BINDING_SHA and v['review_sha256']==review,'exact verified authority')
 need(sha(d/'restore.json')==v['restore_sha256'],'durable restore identity');restore=json.loads((d/'restore.json').read_text());need(restore['row']==row and restore['raw_identity']==v['raw_identity'] and restore['canonical_identity']==v['canonical_identity'],'raw restore join')
 ds=[];result=dict(passed=False,phase='release',batch=batch,row=row,verified_sha256=sha(d/'verified.json'),restore_sha256=v['restore_sha256'],released=False)
 try:
  ds,_=descriptors(row);need(ds[0][2]==v['raw_identity'] and ds[1][2]==v['canonical_identity'],'verified identities unchanged');hashes(ds,row)
  C.save(d/'release-start.json',result)
  for fd,path,st in ds:C.unchanged(fd,path,st)
  os.unlink(ds[0][1]);result['released']=True;C.syncdir(ds[0][1].parent);C.unchanged(*ds[1]);need(not os.path.lexists(ds[0][1]),'only exact raw bundle absent');result['passed']=True
 except BaseException as e:result['error']=repr(e);raise
 finally:
  for fd,_,_ in ds:os.close(fd)
  C.save(d/'released.json',result)
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--verify',action='store_true');g.add_argument('--release-verified',action='store_true');p.add_argument('--batch',type=int);a=p.parse_args()
 if a.plan:
  print(json.dumps(dict(source_only=True,closure_pending=BINDING_SHA is None,rows=mapping(),recoverable_bytes=443486336),indent=2));return
 need(a.batch is not None,'explicit batch');print(json.dumps(verify(a.batch) if a.verify else release(a.batch),indent=2))
if __name__=='__main__':main()
