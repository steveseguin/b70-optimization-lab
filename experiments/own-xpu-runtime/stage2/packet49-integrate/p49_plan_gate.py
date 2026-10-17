"""Actual plan/group construction, metadata only; no arithmetic or weights."""
import gzip,hashlib,json,os,re,subprocess
from pathlib import Path
import plan_group_gate as group
P=Path(__file__).resolve().parent;E=P/'evidence/plan';B=P/'build/p49-plan'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def instrument(code):
 strict=(P/'strict_snapshot.hpp').read_text();proof=strict.split('// SPEED2_WRITE_SET_BEGIN')[1].split('// SPEED2_WRITE_SET_END')[0]+strict.split('// SPEED4_REDO_PROOF_BEGIN')[1].split('// SPEED4_REDO_PROOF_END')[0]
 code=code.replace('argc==6','argc==7').replace('split(full,rank,false,std::string(argv[1])=="KD"?1:dr)', 'split(full,rank,false,std::string(argv[1])=="KD"?1:dr,std::stoi(argv[6]))')
 code='#include "round2.hpp"\n#include "owner_api.hpp"\n#include <sys/mman.h>\n'+code
 code=code.replace('int context=4096,cards=1;', 'int context=4096,cards=1,draft_rank=0,target_split=0;')
 code=code.replace('packet26::dispatch.load(argv[5]);','a.draft_rank=dr;a.target_split=std::stoi(argv[6]);packet26::dispatch.load(argv[5]);')
 runtime=(P/'main.cpp').read_text().split('// SPEED6_SCRATCH_POLICY_BEGIN')[1].split('// SPEED6_SCRATCH_POLICY_END')[0]
 runtime=runtime.replace('pipeline::SnapshotWriteSet','SnapshotWriteSet')
 code=code.replace('struct Probe {',runtime+'\n'+SPARSE_PROOF+'\n'+SCRATCH_PROOF+'\nstruct Probe {')
 code=code.replace('static size_t target_scratch_bytes(',proof+'\n'+WRITE_PROOF+'\nstatic size_t target_scratch_bytes(',1)
 code=code.replace('auto p=draft_plan(full.g);','auto p=draft_plan(full.g);write_proof(p);scratch_allocation_proof(p,a,w,true);')
 needle='Probe e(w,a,std::move(p));std::cout'
 assert code.count(needle)==1
 return code.replace(needle,'''Probe e(w,a,std::move(p));write_proof(e.p);scratch_allocation_proof(e.p,a,w);
 size_t ffns=0,shared=0;std::map<int,size_t> tags;
 for(const auto& [site,g]:e.small_groups)if(g.name.starts_with("small.ffn"))++ffns;
 for(const auto&site:e.p.launches)if(p39::tagged(site)){++tags[int(p39::kind(site))];if(p39::kind(site)==p39::Kind::shared_act)++shared;}
 std::cerr<<"ffn="<<ffns<<" shared="<<shared;
 for(auto[k,v]:tags)std::cerr<<" tag"<<k<<"="<<v;std::cerr<<"\\n";
 std::cout''')


SPARSE_PROOF=r"""
struct SparseOwner final:ownrt::Backend {
 std::map<void*,size_t> sizes;size_t copies=0,maximum=0;
 std::string identity()const override{return "SPEED6 sparse CPU extent proof; no arithmetic";}
 void* allocate(size_t n,ownrt::Memory)override {
  auto p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);
  if(p==MAP_FAILED)throw std::bad_alloc();sizes[p]=n;return p;
 }
 void release(void*p,ownrt::Memory)override{munmap(p,sizes.at(p));sizes.erase(p);}
 ownrt::Event copy(void*,const void*,size_t n,std::span<const ownrt::Event>)override{++copies;maximum=std::max(maximum,n);return ownrt::next_handle();}
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 bool complete(ownrt::Event)override{return true;}
 bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 ownrt::EventTiming timing(ownrt::Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
static void sparse_workspace(const flash::Plan& p,const Weights& w,size_t scratch_bytes){
 auto backend=std::make_unique<SparseOwner>();auto*trace=backend.get();ownrt::Device d(std::move(backend));ownrt::CopyEngine copy(d);
 auto alloc=[&](const char* name,size_t n){return d.arena.allocate(std::string("card0:")+name,n,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);};
 auto scratch=alloc("operator-scratch",scratch_bytes),workspace=alloc("gemv-workspace",8*1024*1024),peer=alloc("extent-peer",256ull*1024*1024);
 size_t peak=0,workspace_peak=0,checks=0;
 auto both=[&](ownrt::Allocation id,size_t n){if(!n)return;copy.copy(id,0,peer,0,n,{});copy.copy(peer,0,id,0,n,{});checks+=2;};
 for(const auto& l:p.launches){
  size_t n=SnapshotWriteSet::scratch(p,l,256ull*1024*1024,true);peak=std::max(peak,n);both(scratch,n);
  if(l.op!="gemv"&&l.op!="routed_gemv"&&l.op!="expert_gate_up")continue;
  require(l.shape.size()==3,"workspace matrix shape");bool routed=l.op!="gemv";
  size_t count=routed?size_t(p.g.top):1,rows=l.shape[1],columns=l.shape[2];
  // P28/P33 full extent contract: eight floats per output row/route.
  size_t need=rows*count*8*4;
  if(routed){
   const auto& tensor=w.directory.at(l.weights[0]);auto grid=iq3::layout(flash::grid_type(tensor.grid));
   require(grid.elements&&columns%grid.elements==0,"workspace quantization block");
   // Conservative union including P25 half-table paired routed scales.
   need=std::max(need,l.weights.size()*count*rows*(columns/std::min(size_t(grid.elements),size_t(32)))*4);
  }
  require(need<=8*1024*1024,"GEMV workspace peak exceeds allocation");workspace_peak=std::max(workspace_peak,need);both(workspace,need);
 }
 require(peak>0&&workspace_peak>0,"empty sparse plan");size_t negatives=0;
 auto reject=[&](ownrt::Allocation id,size_t n){try{copy.copy(id,0,peer,0,n,{});}catch(const std::out_of_range&){++negatives;return;}throw std::runtime_error("short sparse extent accepted");};
 auto short_scratch=alloc("short-scratch",peak-1),short_workspace=alloc("short-workspace",workspace_peak-1);
 reject(short_scratch,peak);reject(short_workspace,workspace_peak);reject(peer,134217729);
 auto end=d.shutdown(std::chrono::seconds(5));require(end.safe_to_exit&&end.exit_code==0,"sparse owner teardown");
 std::cerr<<"SPARSE {\"passed\":true,\"device_executed\":false,\"scratch_peak_bytes\":"<<peak
          <<",\"workspace_peak_bytes\":"<<workspace_peak<<",\"owner_checks\":"<<checks
          <<",\"negative_controls\":"<<negatives<<",\"maximum_copy\":"<<trace->maximum<<"}\n";
}
"""

SCRATCH_PROOF=r"""
static void scratch_allocation_proof(const flash::Plan& p,const Options& a,const Weights& w,bool draft=false){
 constexpr size_t old=256ull*1024*1024,cap=8ull*1024*1024;
 bool reduced=!draft&&a.target_split==23&&a.draft_rank==1&&a.context==4096;
 size_t actual=draft?cap:target_scratch_bytes(p,a); // DraftRuntime already uses 8 MiB.
 require(actual==((draft||reduced)?cap:old),"scratch allocation policy mismatch");
 sparse_workspace(p,w,actual);
 // check_writer_bound uses full kernel scratch_floats requirements, which
 // cover reads as well as writes, for specialised, round2, p33r2 and p42.
 for(const auto& l:p.launches){
  size_t bound=SnapshotWriteSet::scratch(p,l,old,true);
  require(bound<=actual,"allocation below possible writer extent");
  check_writer_bound(p,l,bound);
 }
 auto reference=a;reference.nongemv="core";
 require(target_scratch_bytes(p,reference)==old,"reference scratch shrunk");
 if(reduced){
  auto changed=p;flash::Launch bad;bad.op="unregistered-scratch-reader";changed.launches.push_back(bad);
  bool refused=false;try{(void)target_scratch_bytes(changed,a);}catch(const std::runtime_error&){refused=true;}
  require(refused,"unknown scratch footprint accepted");
  auto wider=p;wider.g.budget=2049;refused=false;
  try{(void)target_scratch_bytes(wider,a);}catch(const std::runtime_error&){refused=true;}
  require(refused,"unregistered geometry accepted");
 }
 std::cerr<<"SCRATCHALLOC {\"bytes\":"<<actual<<",\"draft_private\":"<<(draft?"true":"false")<<",\"reduced\":"<<(reduced?"true":"false")
          <<",\"kernel_read_write_requirements_checked\":true,\"reference_preserved\":true}\n";
}
"""

WRITE_PROOF=r"""
static void check_writer_bound(const flash::Plan& p,const flash::Launch& l,size_t bound){
 ng::Shape s{};s.capacity=p.g.context;s.budget=p.g.budget;s.extent=p.g.context;
 bool check=true;
 size_t n=0;if(!l.inputs.empty())for(const auto& b:p.buffers)if(b.card==l.card&&b.name==l.inputs[0]){n=1;for(int v:b.shape)n*=v;break;}
 if(l.op=="route"){require(bound>=4*(2*((n+15)/16)+2*n),"route writer undercovered");return;}
 if(l.op=="argmax"){require(bound>=8*((n+255)/256),"argmax writer undercovered");return;}
 if(l.op=="expert_gather"){require(bound>=4*size_t(p.g.top),"gather writer undercovered");return;}
 if(l.op=="norm"||l.op=="hc_combine"){s.op=ng::norm;s.width=l.shape.at(1);s.heads=n/s.width;}
 else if(p.g.h!=2560)return;
 else if(l.op=="gdn")s.op=ng::gdn;
 else if(l.op=="gdn_norm_gate")s.op=ng::gated_norm;
 else if(l.op=="qsa_prepare")s.op=ng::prepare;
 else if(l.op=="qsa_append_pool")s.op=ng::pool;
 else if(l.op=="qsa_select")s.op=ng::select;
 else if(l.op=="qsa_attention"){
  require(bound>=16+24*258*((ng::launch_slots(s)+31)/32)*4,"split32 scratch writer undercovered");
  for(auto op:{ng::attention_score,ng::attention_softmax,ng::attention_value}){s.op=op;require(bound>=specialised::scratch_floats(s)*4,"attention writer undercovered");require(bound>=round2::scratch_floats(s)*4,"round2 writer undercovered");}return;
 }else check=false;
 if(check){require(bound>=specialised::scratch_floats(s)*4,"specialised writer undercovered");if(round2::supported(s))require(bound>=round2::scratch_floats(s)*4,"round2 writer undercovered");}
}
static void write_proof(const flash::Plan& p){
 constexpr size_t cap=256ull*1024*1024;
 require(SnapshotWriteSet::scratch(p,cap,false)==cap,"reference fallback");
 flash::Launch unknown;unknown.op="unknown-written-extent";
 require(SnapshotWriteSet::scratch(p,unknown,cap,true)==cap,"unknown writer fallback");
 for(const auto* name:{"route","argmax","norm"}){flash::Launch bad;bad.op=name;require(SnapshotWriteSet::scratch(p,bad,cap,true)==cap,"malformed writer fallback");}
 for(const auto& l:p.launches)if(l.op=="route"||l.op=="argmax"||l.op=="expert_gather"){
  bool rejected=false;try{check_writer_bound(p,l,0);}catch(const std::runtime_error&){rejected=true;}require(rejected,"dropped simple scratch writer escaped proof");
 }
 for(const auto& b:p.buffers)if(SnapshotWriteSet::single_row(p,b.name,true)){
  auto changed=p;flash::Launch alias;alias.op="unproved-writer";alias.outputs={b.name};changed.launches.push_back(alias);
  require(!SnapshotWriteSet::single_row(changed,b.name,true),"second cache writer escaped proof");break;
 }
 std::set<std::string> outputs{"token","position","token_history"};for(const auto& l:p.launches)outputs.insert(l.outputs.begin(),l.outputs.end());
 size_t output_bytes=0,output_count=0;for(const auto& b:p.buffers)if(outputs.count(b.name)){size_t n=flash::scalar_bytes(b.type);for(int d:b.shape)n*=size_t(d);output_bytes+=n;++output_count;}
 std::cerr<<"WRITESET {\"scratch_bound\":"<<SnapshotWriteSet::scratch(p,cap,true)<<",\"plan_output_bytes\":"<<output_bytes<<",\"plan_output_count\":"<<output_count<<",\"context\":"<<p.g.context<<",\"budget\":"<<p.g.budget<<",\"sites\":[";
 bool comma=false;
 for(const auto& l:p.launches){
  check_writer_bound(p,l,SnapshotWriteSet::scratch(p,l,cap,true));
  std::cerr<<(comma?",":"")<<"{\"label\":\""<<l.label<<"\",\"op\":\""<<l.op<<"\",\"scratch_bytes\":"<<SnapshotWriteSet::scratch(p,l,cap,true)<<"}";comma=true;
 }
 std::cerr<<"],\"qsa_rows\":[";comma=false;
 for(const auto& b:p.buffers)if(SnapshotWriteSet::single_row(p,b.name,true)){
  size_t bytes=flash::scalar_bytes(b.type);for(int n:b.shape)bytes*=size_t(n);
  bool pooled=b.name.ends_with(".pooled");size_t rows=pooled?size_t((p.g.context+3)/4):size_t(p.g.context);
  require(bytes%rows==0,"single row geometry");
  std::cerr<<(comma?",":"")<<"{\"name\":\""<<b.name<<"\",\"allocation_bytes\":"<<bytes<<",\"row_bytes\":"<<bytes/rows<<",\"pooled\":"<<(pooled?"true":"false")<<"}";comma=true;
 }
 std::cerr<<"]}\n";
 std::cerr<<"REDOBANK [";comma=false;
 for(const auto& b:p.buffers){auto proof=RedoBankProof::derive(p,b.name);if(!proof.bytes)continue;
  auto l=std::find_if(p.launches.begin(),p.launches.end(),[&](const auto& x){return x.label==proof.writer;});require(l!=p.launches.end(),"missing first writer");
  ng::Shape shape{};shape.tokens=1;shape.capacity=p.g.context;shape.extent=p.g.context;shape.budget=p.g.budget;
  shape.op=l->op=="gdn"?ng::gdn:ng::conv;shape.width=l->shape[0];shape.extra=l->parameter;
  require(ng::required_bytes(shape)[l->op=="gdn"?7:4]==proof.bytes,"redo kernel byte coverage");
  auto partial=p;for(auto& x:partial.buffers)if(x.name==b.name)++x.shape.back();require(!RedoBankProof::derive(partial,b.name).bytes,"partial write coverage accepted");
  auto duplicate=p;duplicate.launches.push_back(*l);require(!RedoBankProof::derive(duplicate,b.name).bytes,"multiple writers accepted");
  auto unknown=p;for(auto& x:unknown.launches)if(x.label==proof.writer)x.op="unknown";require(!RedoBankProof::derive(unknown,b.name).bytes,"unknown writer accepted");
  std::cerr<<(comma?",":"")<<"{\"name\":\""<<b.name<<"\",\"first_writer\":\""<<proof.writer<<"\",\"bytes\":"<<proof.bytes<<",\"full_byte_coverage\":true,\"inputs_use_distinct_active_bank\":true}";comma=true;
 }
 std::cerr<<"]\n";
}
"""

def main():
 from datetime import datetime,timezone
 assert datetime.now(timezone.utc)>=datetime(2026,10,15,5,15,tzinfo=timezone.utc),'owner build hold until 05:15 UTC'
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 E.mkdir(exist_ok=True);B.mkdir(exist_ok=True);group.B=B;group.E=E
 # Link only the real owner guard into the metadata-only sparse probe.
 from unittest.mock import patch
 run_compile=group.subprocess.run
 def with_owner(command,**kwargs):
  command=list(command);at=command.index('-o')
  command[at:at]=[str(P/'owner.cpp'),str(P/'owner_retire.cpp')]
  return run_compile(command,**kwargs)
 with patch.object(group.subprocess,'run',side_effect=with_owner):group.generate('after',instrument)
 rows=[]
 for context in (4096,):
  for dr,split in ((1,23),):
   for kind,rank in [('target',0),('target',1),('KD',1),('draft',dr)]:
    for dispatch in ('dr0','speed6','forced'):
     path=P/'dispatch-speed6.json' if dispatch=='speed6' else P.parent/f'packet45-merged3/evidence/fix6/dispatch-{dispatch}.json'
     cmd=[str(B/'after'),kind,str(context),str(dr),str(rank),str(path),str(split)]
     run=subprocess.run(cmd,text=True,capture_output=True);result=json.loads(run.stdout)
     footprint=json.loads(next(x.removeprefix('WRITESET ') for x in run.stderr.splitlines() if x.startswith('WRITESET ')))
     assert run.returncode==0 and result['passed'],run.stderr+run.stdout
     footprint['redo_banks']=json.loads(next(x.removeprefix('REDOBANK ') for x in run.stderr.splitlines() if x.startswith('REDOBANK ')))
     allocation=json.loads(next(x.removeprefix('SCRATCHALLOC ') for x in run.stderr.splitlines() if x.startswith('SCRATCHALLOC ')))
     sparse=json.loads(next(x.removeprefix('SPARSE ') for x in run.stderr.splitlines() if x.startswith('SPARSE ')))
     counts={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',run.stderr)}
     if kind!='draft':
      boundary=split or (24 if kind=='KD' or dr else 22)
      layers=boundary if rank==0 else 48-boundary
      assert counts['ffn']==layers and counts['shared']==0,(kind,dr,rank,counts)
     rows.append(dict(plan=kind,context=context,draft_rank=dr,target_split=split,rank=rank,dispatch=dispatch,
                      dispatch_sha256=sha(path),result=result,group_census=counts,write_set=footprint,scratch_allocation=allocation,sparse_workspace=sparse))
 for c in (4096,):
  for dr,split in ((1,23),):
   for dispatch in ('dr0','speed6','forced'):
    target=[r for r in rows if (r['context'],r['draft_rank'],r['target_split'],r['dispatch'],r['plan'])==(c,dr,split,dispatch,'target')]
    assert sum(r['group_census']['ffn'] for r in target)==48
 details=[]
 for r in rows:
  sites=r['write_set'].pop('sites');r['write_set']['sites_count']=len(sites)
  r['write_set']['sites_sha256']=hashlib.sha256(json.dumps(sites,sort_keys=True).encode()).hexdigest()
  details.append(dict(plan=r['plan'],context=r['context'],draft_rank=r['draft_rank'],target_split=r['target_split'],rank=r['rank'],dispatch=r['dispatch'],sites=sites))
 detailed=E/'plan-writer-sites.json.gz';detailed.write_bytes(gzip.compress(json.dumps(details,sort_keys=True).encode(),mtime=0))
 sources=('owner.cpp','owner_retire.cpp','owner_api.hpp','p25_bridge.cpp','p28/submit.cpp','p33r2.cpp','p42_submit.cpp','strict_snapshot.hpp','adapter.cpp','specialised.hpp','kernels.hpp','round2_submit.cpp','round2.hpp','p42_cooperative.hpp','p42_tiny.hpp','p33r2.hpp','route42.hpp','p49_plan_gate.py','plan_group_gate.py','main.cpp','rank.hpp','mtp.hpp','p39_plan.hpp','small_gemv.cpp','small_gemv.hpp')
 report=dict(passed=True,device_executed=False,weight_bytes_read=0,plan_dispatch_rows=len(rows),
  writer_sites=dict(path=str(detailed.relative_to(P)),sha256=sha(detailed),rows=len(details)),target_ffn_groups=48,commands_per_tuple_before=6,commands_per_tuple_after=2,
  removed_target_commands=192,command_count_scope='48 restored groups times the retained six-to-two command recipes; no model execution',
  sources_sha256={n:sha(P/n) for n in sources},metadata_sha256=sha(P/'build/input/plan.tsv'),
  binary_sha256=sha(B/'after'),generated_sha256=sha(B/'after.cpp'),rows=rows)
 (P/'p49-plan-gates.json').write_text(json.dumps(report,indent=2)+'\n')
 (E/'plan-sweep.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('rows','sources_sha256')}))
if __name__=='__main__':main()
