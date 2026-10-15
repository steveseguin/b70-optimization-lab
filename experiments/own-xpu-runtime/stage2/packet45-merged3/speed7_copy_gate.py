"""Production-size sparse owner copies using the extracted runtime batch loop.

Reads retained allocation/plan metadata only. No weights or device binary.
Temporary probe is archived, then removed; allocations use MAP_NORESERVE.
"""
import gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed7';LIMIT=134217728

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def old_schedule(sizes):
 out=[];batch=[]
 for n in sorted(min(LIMIT,n-off) for n in sizes for off in range(0,n,LIMIT)):
  if batch and (len(batch)==32 or sum(batch)+n>LIMIT):out.append(batch);batch=[]
  batch.append(n)
 if batch:out.append(batch)
 return dict(batches=len(out),padded_byte_slots=sum(len(b)*((max(b)+15)//16)*16 for b in out),bytes=sum(map(sum,out)))

def probe_source():
 source=(P/'strict_snapshot.hpp').read_text()
 batch=source[source.index('#ifdef OWN_RT_HOST_ONLY'):source.index('// SPEED2_WRITE_SET_BEGIN')]
 loop=source[source.index('  std::vector<size_t> order(lengths.size())'):source.index('  (restore?restore_submissions:capture_submissions)+=submissions;')]
 loop=loop.replace('e.tail=e.dev(0).','tail=d.').replace('++submissions;', '++submissions; padded+=batch.count*((batch.maximum+15)/16)*16; largest=std::max(largest,batch.total);')
 loop=loop.replace('const auto& item=checked[i];','require(++seen[i]==1,"duplicate descriptor");const auto& item=checked[i];')
 return r'''
#define OWN_RT_HOST_ONLY 1
#include "owner_api.hpp"
#include <sys/mman.h>
#include <iostream>
#include <numeric>
#include <cstring>
#include <map>
namespace integrated {struct HostOperation:ownrt::Operation {virtual void run(std::span<void*const>)const=0;};}
static void require(bool b,const char*s){if(!b)throw std::runtime_error(s);}
'''+batch+r'''
struct Sparse:ownrt::Backend {
 std::map<void*,size_t> sizes;size_t copies=0;
 std::string identity()const override{return "SPEED7 sparse host; no device";}
 void* allocate(size_t n,ownrt::Memory)override{auto p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);if(p==MAP_FAILED)throw std::bad_alloc();sizes[p]=n;return p;}
 void release(void*p,ownrt::Memory)override{munmap(p,sizes.at(p));sizes.erase(p);}
 ownrt::Event copy(void*d,const void*s,size_t n,std::span<const ownrt::Event>)override{std::memcpy(d,s,n);++copies;return ownrt::next_handle();}
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 ownrt::Event compute(const ownrt::Operation&op,std::span<void*const>p,std::span<const ownrt::Event>)override{dynamic_cast<const integrated::HostOperation&>(op).run(p);return ownrt::next_handle();}
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation>op,std::span<void*const>p)override{std::vector<void*> v(p.begin(),p.end());return [this,op,v]{return compute(*op,v,{});};}
 bool complete(ownrt::Event)override{return true;}bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 ownrt::EventTiming timing(ownrt::Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
static void batches(ownrt::Device& d,std::vector<ownrt::PreparedCompute>&checked,const std::vector<size_t>&lengths){
 using ownrt::Allocation;ownrt::Event tail=0;size_t padded=0,largest=0;std::vector<size_t>seen(lengths.size());
'''+loop+r'''
 require(std::all_of(seen.begin(),seen.end(),[](size_t n){return n==1;}),"lost descriptor");
 require(d.wait(tail,std::chrono::seconds(5)),"drain");d.retire_completed_events();
 std::cout<<"{\"batches\":"<<submissions<<",\"padded_byte_slots\":"<<padded<<",\"largest_submission_bytes\":"<<largest<<",\"components\":"<<lengths.size()<<",\"bytes\":"<<std::accumulate(lengths.begin(),lengths.end(),size_t(0))<<"}";
}
int main(){
 auto backend=std::make_unique<Sparse>();ownrt::Device d(std::move(backend));ownrt::CopyEngine copy(d);
 struct Extent {ownrt::Allocation id;size_t full,off,n,back;bool bank;};std::vector<Extent>xs;size_t full,off,n,bank,capacity=0;
 while(std::cin>>full>>off>>n>>bank){require(n&&off<=full&&n<=full-off,"input extent");auto id=d.arena.allocate("card0:source"+std::to_string(xs.size()),full,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);xs.push_back({id,full,off,n,capacity,bool(bank)});capacity+=full;}
 auto backup=d.arena.allocate("card0:backup",capacity,ownrt::Memory::device,ownrt::Category::runtime_overhead,ownrt::Lifetime::process);
 for(auto&x:xs){auto*p=static_cast<unsigned char*>(d.arena.row(x.id).pointer);std::memset(p+x.off,0x35,x.n);if(x.off)p[x.off-1]=0x71;if(x.off+x.n<x.full)p[x.off+x.n]=0x72;}
 std::cout<<"{\"phases\":{";
 for(int mode=0;mode<4;++mode){
  if(mode)std::cout<<",";std::cout<<"\""<<(mode==0?"capture":mode==1?"full_restore":mode==2?"redo_restore":"deferred_restore")<<"\":";
  std::vector<ownrt::PreparedCompute>checked;std::vector<size_t>lengths;d.begin_capture(checked);
  for(auto&x:xs){if(mode==2&&x.bank)continue;if(mode==3&&!x.bank)continue;
   if(mode)std::memset(static_cast<unsigned char*>(d.arena.row(x.id).pointer)+x.off,0x58,x.n);
   for(size_t pos=0;pos<x.n;pos+=SnapshotBatch::limit){size_t count=std::min(x.n-pos,SnapshotBatch::limit);
    if(mode)copy.copy(x.id,x.off+pos,backup,x.back+pos,count,{});else copy.copy(backup,x.back+pos,x.id,x.off+pos,count,{});lengths.push_back(count);
   }
  }d.end_capture();require(checked.size()==lengths.size(),"capture count");batches(d,checked,lengths);
  for(auto&x:xs){auto*p=static_cast<unsigned char*>(d.arena.row(x.id).pointer);auto*b=static_cast<unsigned char*>(d.arena.row(backup).pointer)+x.back;
   require(std::memcmp(p+x.off,b,x.n)==0,"production byte comparison");if(x.off)require(p[x.off-1]==0x71,"prefix changed");if(x.off+x.n<x.full)require(p[x.off+x.n]==0x72,"suffix changed");}
 }
 size_t negatives=0;auto&x=xs.front();auto reject=[&](size_t a,size_t b,size_t n){try{copy.copy(x.id,a,backup,b,n,{});}catch(const std::out_of_range&){++negatives;return;}throw std::runtime_error("invalid copy accepted");};
 reject(0,0,0);reject(0,0,134217729);reject(x.full,0,1);reject(0,capacity,1);
 auto*p=static_cast<unsigned char*>(d.arena.row(x.id).pointer)+x.off;auto*b=static_cast<unsigned char*>(d.arena.row(backup).pointer)+x.back;*p^=1;require(std::memcmp(p,b,x.n)!=0,"dropped written byte not detected");++negatives;
 SnapshotBatch policy;policy.count=1;policy.total=1;require(policy.accepts(8,1)&&!policy.accepts(9,1),"ratio boundary");policy.count=32;require(!policy.accepts(1,1),"width boundary");policy.count=1;policy.total=SnapshotBatch::limit;require(!policy.accepts(1,1),"sum boundary");
 auto end=d.shutdown(std::chrono::seconds(5));require(end.safe_to_exit&&end.exit_code==0,"safe shutdown");
 std::cout<<"},\"negative_controls\":"<<negatives<<",\"policy_boundaries\":3,\"passed\":true}\n";
}
'''

def verify():
 r=json.loads((P/'speed7-copy-gates.json').read_text())
 assert r['passed'] and r['device_executed'] is False and r['weight_bytes_read']==0
 assert r['additional_device_allocation_bytes']==0 and r['temporary_probe_removed']
 assert r['plan_gate_sha256']==sha(P/'speed7-plan-gates.json')
 for field in ('input_sha256','source_sha256'):
  for name,h in r[field].items():assert sha(P/name)==h,'copy proof input changed: '+name
 for key in ('probe_archive','extents_archive'):
  assert sha(P/r[key]['path'])==r[key]['sha256']
 generated=gzip.decompress((P/r['probe_archive']['path']).read_bytes())
 assert generated.decode()==probe_source() and hashlib.sha256(generated).hexdigest()==r['generated_sha256']
 details=json.loads(gzip.decompress((P/r['extents_archive']['path']).read_bytes()))
 expected={(c,dr,s,pos) for c in (4096,32768) for dr,s in ((0,0),(0,24),(1,24),(1,23)) for pos in (100,128,214)}
 assert r['production_rows']==len(r['rows'])==len(details)==24
 assert {(x['context'],x['draft_rank'],x['target_split'],x['position']) for x in r['rows']}==expected
 assert r['copy_phases']==96 and r['negative_controls']==120 and r['policy_boundaries']==72
 sweep=json.loads((P/'speed7-plan-gates.json').read_text())
 roots={(0,0):'results-f912fdaf6/c4096-dr0-gpu',(0,24):'speed3-c4096-dr0-s24-gpu',(1,24):'speed3-c4096-dr1-gpu',(1,23):'speed6-c4096-dr1-s23-cards01-gpu'}
 metadata={}
 for key,run in roots.items():
  root=P/'build'/run/'WS128/run/ranks/rank0'
  assert all(str((root/name).relative_to(P)) in r['input_sha256'] for name in ('census.json','launch-plan.json'))
  allocations=json.loads((root/'census.json').read_text())['allocations'];plan=json.loads((root/'launch-plan.json').read_text())
  backup=next(x for x in allocations if x['label']=='card0:speculative-private-image')
  outputs={'token','position','token_history'};kv=set()
  for site in plan['launches']:
   outputs.update(site['outputs'])
   if site['op']=='qsa_append_pool':kv.update(site['outputs'])
  represented={'card0:'+x['name'] for x in plan['buffers']}|{x['label'] for x in allocations if x['label'].startswith('card0:alternate:')}
  sources=[(x['name'],x['bytes']) for x in plan['buffers'] if x['name'] in outputs]
  sources += [(x['label'],x['bytes']) for x in allocations if x['id']<backup['id'] and x['live'] and x['memory']=='device' and x['category']!='weights' and x['label'] not in represented and x['label']!='card0:mixture-one']
  assert sum(n for _,n in sources)==backup['bytes']
  metadata[key]=(sources,kv)
 for row,detail in zip(r['rows'],details):
  assert all(row[k]==detail[k] for k in ('context','draft_rank','target_split','position'))
  sources,kv=metadata[row['draft_rank'],row['target_split']]
  matches=[v for v in sweep['rows'] if v['plan']=='target' and v['rank']==0 and all(v[k]==row[k] for k in ('context','draft_rank','target_split'))]
  assert len(matches)==3
  footprint=matches[0]['write_set'];qsa={x['name']:x for x in footprint['qsa_rows']};banks={x['name']:x for x in footprint['redo_banks']}
  assert all(all(v['write_set'][k]==footprint[k] for k in ('scratch_bound','qsa_rows','redo_banks','plan_output_count','plan_output_bytes')) for v in matches)
  current=[(name,n) for name,n in sources if not name.startswith('card0:')]
  assert len(current)==footprint['plan_output_count']
  assert sum(qsa[name]['allocation_bytes'] if name in kv else n for name,n in current)==footprint['plan_output_bytes']
  expected_extents=[]
  for name,full in sources:
   offset=0;n=full
   if name in kv:
    q=qsa[name];full=q['allocation_bytes'];n=q['row_bytes'];offset=(row['position']//4 if q['pooled'] else row['position'])*n
   elif name=='card0:operator-scratch':n=footprint['scratch_bound']
   if name in banks:assert n==banks[name]['bytes']
   expected_extents.append(dict(name=name,full=full,offset=offset,bytes=n,redo_overwritten=name in banks))
  assert detail['extents']==expected_extents,'copy extent set differs from production metadata and writer proof'

  assert row['passed'] and row['negative_controls']==5 and row['policy_boundaries']==3
  assert set(row['phases'])=={'capture','full_restore','redo_restore','deferred_restore'}
  for phase,new in row['phases'].items():
   xs=[x for x in detail['extents'] if (phase!='redo_restore' or not x['redo_overwritten']) and (phase!='deferred_restore' or x['redo_overwritten'])]
   assert all(0<x['bytes']<=x['full']-x['offset'] and x['offset']>=0 for x in xs)
   sizes=[x['bytes'] for x in xs];old=old_schedule(sizes);old['padding_bytes']=old['padded_byte_slots']-old['bytes']
   assert new['before']==old and new['bytes']==sum(sizes)==old['bytes']
   batches=[];batch=[]
   for n in sorted(min(LIMIT,x-off) for x in sizes for off in range(0,x,LIMIT)):
    if batch and (len(batch)==32 or sum(batch)+n>LIMIT or n>batch[0]*8):batches.append(batch);batch=[]
    batch.append(n)
   if batch:batches.append(batch)
   assert new['batches']==len(batches) and new['components']==sum(map(len,batches))
   assert new['largest_submission_bytes']==max(map(sum,batches))<=LIMIT
   assert new['padded_byte_slots']==sum(len(b)*((max(b)+15)//16)*16 for b in batches)<=old['padded_byte_slots']
   assert new['padding_bytes']==new['padded_byte_slots']-new['bytes']
  assert row['phases']['capture']==row['phases']['full_restore']
  assert row['phases']['capture']['bytes']==row['phases']['redo_restore']['bytes']+row['phases']['deferred_restore']['bytes']
 return r

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 sweep=json.loads((P/'speed7-plan-gates.json').read_text());pins={};rows=[];proof=[]
 def read(path):pins[str(path.relative_to(P))]=sha(path);return json.loads(path.read_text())
 configs=((0,0,'results-f912fdaf6/c4096-dr0-gpu'),(0,24,'speed3-c4096-dr0-s24-gpu'),(1,24,'speed3-c4096-dr1-gpu'),(1,23,'speed6-c4096-dr1-s23-cards01-gpu'))
 scratch=Path(tempfile.mkdtemp(prefix='speed7-copy-',dir=P/'build'))
 try:
  source=scratch/'probe.cpp';source.write_text(probe_source());binary=scratch/'probe'
  command=['g++','-std=c++20','-O1','-fno-fast-math','-ffp-contract=off','-I'+str(P),str(source),str(P/'owner.cpp'),str(P/'owner_retire.cpp'),'-o',str(binary)]
  with (E/'copy-compile.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
  generated_sha=sha(source);binary_sha=sha(binary)
  for dr,split,run in configs:
   root=P/'build'/run/'WS128/run/ranks/rank0';alloc=read(root/'census.json')['allocations'];plan=read(root/'launch-plan.json')
   backup=next(x for x in alloc if x['label']=='card0:speculative-private-image')
   represented={'card0:'+x['name'] for x in plan['buffers']}|{x['label'] for x in alloc if x['label'].startswith('card0:alternate:')}
   outputs={'token','position','token_history'};kv=set()
   for site in plan['launches']:
    outputs.update(site['outputs'])
    if site['op']=='qsa_append_pool':kv.update(site['outputs'])
   sources=[dict(name=x['name'],bytes=x['bytes']) for x in plan['buffers'] if x['name'] in outputs]
   sources += [dict(name=x['label'],bytes=x['bytes']) for x in alloc if x['id']<backup['id'] and x['live'] and x['memory']=='device' and x['category']!='weights' and x['label'] not in represented and x['label']!='card0:mixture-one']
   assert sum(x['bytes'] for x in sources)==backup['bytes']
   for context in (4096,32768):
    matches=[r for r in sweep['rows'] if (r['context'],r['draft_rank'],r['target_split'],r['plan'],r['rank'])==(context,dr,split,'target',0)]
    assert len(matches)==3
    footprint=matches[0]['write_set'];assert all(all(r['write_set'][key]==footprint[key] for key in ('scratch_bound','qsa_rows','redo_banks','plan_output_count','plan_output_bytes')) for r in matches)
    qsa={r['name']:r for r in footprint['qsa_rows']};banks={r['name']:r for r in footprint['redo_banks']}
    plan_outputs=[x for x in sources if not x['name'].startswith('card0:')]
    assert len(plan_outputs)==footprint['plan_output_count']
    assert sum(qsa[x['name']]['allocation_bytes'] if x['name'] in kv else x['bytes'] for x in plan_outputs)==footprint['plan_output_bytes']
    for position in (100,128,214):
     extents=[]
     for x in sources:
      name=x['name'];full=x['bytes'];offset=0;n=full
      if name in kv:
       q=qsa[name];full=q['allocation_bytes'];n=q['row_bytes'];offset=(position//4 if q['pooled'] else position)*n
      elif name=='card0:operator-scratch':n=footprint['scratch_bound']
      if name in banks:assert n==banks[name]['bytes']
      extents.append(dict(name=name,full=full,offset=offset,bytes=n,redo_overwritten=name in banks))
     result=subprocess.run([str(binary)],input=''.join(f"{x['full']} {x['offset']} {x['bytes']} {int(x['redo_overwritten'])}\n" for x in extents),capture_output=True,text=True)
     assert result.returncode==0,result.stderr
     after=json.loads(result.stdout);assert after['passed'] and after['negative_controls']==5
     for phase,new in after['phases'].items():
      sizes=[x['bytes'] for x in extents if (phase!='redo_restore' or not x['redo_overwritten']) and (phase!='deferred_restore' or x['redo_overwritten'])]
      before=old_schedule(sizes);assert new['bytes']==before['bytes'] and new['largest_submission_bytes']<=LIMIT
      assert new['padded_byte_slots']<=before['padded_byte_slots']
      new['before']=before;new['padding_bytes']=new['padded_byte_slots']-new['bytes'];before['padding_bytes']=before['padded_byte_slots']-before['bytes']
     row=dict(context=context,draft_rank=dr,target_split=split,position=position,**after);rows.append(row);proof.append(dict(context=context,draft_rank=dr,target_split=split,position=position,extents=extents))
  archived=E/'copy-probe.cpp.gz';archived.write_bytes(gzip.compress(source.read_bytes(),mtime=0))
  detail=E/'copy-extents.json.gz';detail.write_bytes(gzip.compress(json.dumps(proof,sort_keys=True).encode(),mtime=0))
  receipt=dict(passed=True,device_executed=False,weight_bytes_read=0,rows=rows,production_rows=len(rows),copy_phases=sum(len(r['phases']) for r in rows),negative_controls=sum(r['negative_controls'] for r in rows),policy_boundaries=sum(r['policy_boundaries'] for r in rows),input_sha256=pins,source_sha256={n:sha(P/n) for n in ('strict_snapshot.hpp','owner.cpp','owner_retire.cpp','owner_api.hpp','speed7_copy_gate.py')},plan_gate_sha256=sha(P/'speed7-plan-gates.json'),generated_sha256=generated_sha,binary_sha256=binary_sha,probe_archive=dict(path=str(archived.relative_to(P)),sha256=sha(archived)),extents_archive=dict(path=str(detail.relative_to(P)),sha256=sha(detail)),temporary_probe_removed=True,additional_device_allocation_bytes=0,meaning='Actual extracted host batch loop and owner guard; full payload memcmp on sparse production allocations. Padded byte slots describe dispatch geometry, not transferred or allocated bytes.')
  (P/'speed7-copy-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
  print(json.dumps({k:v for k,v in receipt.items() if k not in ('rows','input_sha256','source_sha256')},indent=2))
 finally:shutil.rmtree(scratch)
if __name__=='__main__':main()
