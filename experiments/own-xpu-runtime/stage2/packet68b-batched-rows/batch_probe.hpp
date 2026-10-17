#pragma once
#include "batched_hc.hpp"
#include "batched_experts.hpp"
namespace p68b {
using Commands=std::vector<ownrt::PreparedCompute>;
using Schedule=std::vector<Commands>;
using Map=std::map<Allocation,Allocation>;
// Clone only mutable allocations; the original weight allocation is shared.
// Every operation is captured outside its timed replay. Real bindings and
// prepared callbacks are restored before the ordinary half resumes.
struct RowScope {
 Engine&e;decltype(e.buffers) buffers;decltype(e.prepared) prepared;decltype(e.matrices) matrices;
 decltype(e.state_spares) spares;std::vector<Allocation>scratch,workspace,controls,scores,probabilities,mixture,fp32,sources;std::vector<size_t>extents;
 RowScope(Engine&v,const Map&m):e(v),buffers(e.buffers),prepared(std::move(e.prepared)),matrices(std::move(e.matrices)),spares(e.state_spares),scratch(e.scratch),workspace(e.workspace),controls(e.controls),scores(e.scores),probabilities(e.probabilities),mixture(e.mixture_out),fp32(e.fp32_inputs),sources(e.fp32_sources),extents(e.fp32_extents){
  auto remap=[&](auto&ids){for(auto&id:ids)id=m.at(id);};for(auto&[name,s]:e.buffers[0])s.id=m.at(s.id);for(auto&[name,id]:e.state_spares)id=m.at(id);
  remap(e.scratch);remap(e.workspace);remap(e.controls);remap(e.scores);remap(e.probabilities);remap(e.mixture_out);remap(e.fp32_inputs);std::fill(e.fp32_sources.begin(),e.fp32_sources.end(),0);e.prepared.clear();e.matrices.clear();e.prepare_plan();
 }
 ~RowScope(){e.buffers=std::move(buffers);e.prepared=std::move(prepared);e.matrices=std::move(matrices);e.state_spares=std::move(spares);e.scratch=scratch;e.workspace=workspace;e.controls=controls;e.scores=scores;e.probabilities=probabilities;e.mixture_out=mixture;e.fp32_inputs=fp32;e.fp32_sources=sources;e.fp32_extents=extents;}
};
struct Compare final:Base {
 size_t bytes=0;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{if(std::memcmp(p[0],p[1],bytes))*(uint32_t*)p[2]=1;}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{auto a=(const uint8_t*)p[0],b=(const uint8_t*)p[1];auto status=(uint32_t*)p[2];auto n=bytes;return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::range<1>((n+15)/16),[=](sycl::id<1>id){size_t off=id[0]*16;bool diff=false;for(unsigned j=0;j<16&&off+j<n;++j)diff|=a[off+j]!=b[off+j];if(diff)sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*status).store(1);});});}
#endif
};
struct Probe {
 Engine&e;std::array<Map,3> maps;std::map<Allocation,size_t> clone_sizes;Allocation status=0;size_t clone_bytes=0;unsigned sample=0;std::ofstream log;
 explicit Probe(Engine&v):e(v),log(e.a.output/"batched-rows.jsonl"){
  std::set<Allocation> ids;for(auto&[name,s]:e.buffers[0])ids.insert(s.id);for(auto&[name,id]:e.state_spares)ids.insert(id);
  for(auto list:{e.scratch,e.workspace,e.controls,e.scores,e.probabilities,e.mixture_out,e.fp32_inputs})for(auto id:list)ids.insert(id);
  for(auto id:ids){size_t n=e.dev(0).arena.row(id).bytes;
   if(id==e.scratch[0])n=std::min(n,std::max(size_t(8*1024*1024),pipeline::SnapshotWriteSet::scratch(e.p,n,true)));
   clone_sizes[id]=n;clone_bytes+=n*3;
  }
  require(clone_bytes+4<=512ull*1024*1024,"68b clone budget exceeds 512 MiB per rank");
  for(unsigned r=0;r<3;++r)for(auto id:ids){auto row=e.dev(0).arena.row(id);maps[r][id]=e.allocate(0,"68b-row"+std::to_string(r)+":"+row.label,clone_sizes.at(id),Category::runtime_overhead,Lifetime::process);}
  status=e.allocate(0,"68b-byte-identity",4,Category::runtime_overhead,Lifetime::process);
 }
 Schedule ordinary(unsigned row){RowScope scope(e,maps[row]);Schedule out(e.p.launches.size());for(size_t i=0;i<out.size();++i){e.preparing_commands=true;e.dev(0).begin_capture(out[i]);try{e.execute_site(e.p.launches[i]);e.dev(0).end_capture();e.preparing_commands=false;}catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}}return out;}
 integrated::Matrix mapped(const flash::Launch&l,unsigned row,size_t projection=0){auto m=e.matrices.at(&l).at(projection);m.x=maps[row].at(m.x);m.y=maps[row].at(m.y);m.workspace=maps[row].at(m.workspace);if(m.routes)m.routes=maps[row].at(m.routes);if(m.status)m.status=maps[row].at(m.status);return m;}
 p60::IDs hc_ids(const flash::Launch&l,unsigned row){
  const std::string tag=l.label.substr(0,l.label.rfind('.')),prefix=tag.substr(0,tag.find(".hc.")),wt=prefix+(tag.ends_with(".a")?".hc_attn_":".hc_ffn_");
  auto id=[&](const std::string&n){return maps[row].at(e.buffers[0].at(n).id);};auto w=[&](const std::string&n){return e.weights[0].at(wt+n+".weight");};
  return {id("streams"),w("norm"),w("down"),w("up"),w("inject"),id(tag+".norm"),id(tag+".low"),id(tag+".act"),id(tag+".gate"),id(tag+".mix"),id(tag+".inject"),maps[row].at(e.scratch[0]),maps[row].at(e.workspace[0]),id("error"),id("active"),id("position")};
 }
 bool paired_site(const flash::Launch&l){
  int stage=p60::stage(l.label);if(stage>=0){if(stage!=3)hc(e.dev(0),hc_ids(l,1),hc_ids(l,2),stage,e.p.g.context);return true;}
  if(e.small_followers.count(&l))return true;
  if(p49b_site(e.w,e.a,l)){
   std::vector<integrated::Matrix>a{mapped(l,1)},b{mapped(l,2)};
   if(l.op=="expert_gate_up"){a.push_back(mapped(l,1,1));b.push_back(mapped(l,2,1));}
   std::array<Allocation,2>error{maps[1].at(e.buffers[0].at("error").id),maps[2].at(e.buffers[0].at("error").id)},active{maps[1].at(e.buffers[0].at("active").id),maps[2].at(e.buffers[0].at("active").id)};
   experts(e.dev(0),a,b,error,active);return true;
  }
  if(l.op!="gemv")return false;
  if(p39::tagged(l)&&p39::kind(l)!=p39::Kind::silu_div4&&p39::kind(l)!=p39::Kind::attention_combine&&p39::kind(l)!=p39::Kind::shared_act)return false;
  std::vector<integrated::Matrix>a,b;std::vector<unsigned>vs;
  if(auto g=e.small_groups.find(&l);g!=e.small_groups.end()){for(auto*member:g->second.members){a.push_back(mapped(*member,1));b.push_back(mapped(*member,2));vs.push_back(e.variant(*member));}}
  else {a.push_back(mapped(l,1));b.push_back(mapped(l,2));vs.push_back(e.variant(l));}
  dense(e.dev(0),a,b,vs);
  if(p39::tagged(l)){
   auto kind=p39::kind(l);auto cls=packet26::Dispatch::class_name(l.label),prefix=l.label.substr(0,l.label.size()-cls.size());Tail tail;tail.kind=kind;tail.rows=a[0].rows;tail.capacity=e.p.g.context;std::array<Allocation,14>ids;
   for(unsigned r=0;r<2;++r){auto id=[&](const std::string&n){return maps[r+1].at(e.buffers[0].at(n).id);};auto y=r?b[0].y:a[0].y;Allocation out=y,other=y;
    if(kind==p39::Kind::silu_div4)out=id(l.label.substr(0,l.label.size()-3)+"act");
    if(kind==p39::Kind::attention_combine){out=id("streams");other=id(prefix+"hc.a.inject");}
    if(kind==p39::Kind::shared_act){out=id(prefix+"shexpact");other=id(prefix+"shexpgate");}
    std::array<Allocation,7>v{y,out,other,id("error"),id("active"),id("position"),y};std::copy(v.begin(),v.end(),ids.begin()+r*7);
   }e.dev(0).compute(tail,ids,{});
  }return true;
 }
 struct Timing {double wall=0,span=0,sum=0;std::map<std::string,double>classes;};
 Timing replay(const Schedule&schedule){
  Timing t;std::vector<std::pair<ownrt::Event,size_t>>events;auto started=std::chrono::steady_clock::now();
  for(size_t i=0;i<schedule.size();++i){for(auto&cmd:schedule[i]){auto event=e.dev(0).issue(cmd);e.tail=event;events.emplace_back(event,i);}pipeline_cancel_check();}
  if(e.tail)e.wait(0,e.tail);t.wall=Engine::ms(started);
#ifndef OWN_RT_HOST_ONLY
  uint64_t first=0,last=0;for(auto[event,i]:events){auto time=e.dev(0).timing(event);require(time.start_ns&&time.end_ns>=time.start_ns&&time.end_ns-time.start_ns<4000000000ull,"68b event bound");if(!first)first=time.start_ns;last=time.end_ns;double ms=(time.end_ns-time.start_ns)/1e6;t.sum+=ms;t.classes[packet26::Dispatch::class_name(e.p.launches[i].label)]+=ms;}t.span=(last-first)/1e6;
#endif
  e.tail=0;e.dev(0).retire_completed_events();return t;
 }
 void run(int fixture,int position){
  // Finish queued draft work and publish it before private replay can retire
  // its event IDs. This is a diagnostic boundary, outside publication callbacks.
  if(e.tail)e.wait(0,e.tail);if(e.progress_pending&&e.progress_callback)e.progress_callback();require(!e.progress_pending,"68b outstanding draft publication");e.drain();
  auto copy_start=std::chrono::steady_clock::now();ownrt::CopyEngine copy(e.dev(0));
  for(auto&m:maps)for(auto[src,dst]:m){size_t bytes=clone_sizes.at(src);for(size_t off=0;off<bytes;off+=64*1024*1024)e.tail=copy.copy(dst,off,src,off,std::min(size_t(64*1024*1024),bytes-off),{});}e.drain();double copy_ms=Engine::ms(copy_start);
  auto one=ordinary(0),left=ordinary(1),right=ordinary(2);Schedule two(one.size());std::set<std::string>batched,serial;
  for(size_t i=0;i<two.size();++i){e.preparing_commands=true;e.dev(0).begin_capture(two[i]);bool paired=false;try{paired=paired_site(e.p.launches[i]);e.dev(0).end_capture();e.preparing_commands=false;}catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}
   auto name=packet26::Dispatch::class_name(e.p.launches[i].label);if(paired)batched.insert(name);else {two[i]=left[i];two[i].insert(two[i].end(),right[i].begin(),right[i].end());serial.insert(name);}}
  Timing h1,h2;bool reverse=sample++%2;if(reverse){h2=replay(two);h1=replay(one);}else{h1=replay(one);h2=replay(two);}
  // Compare both private outputs, all persistent plan bytes and spare banks.
  // Scratch is intentionally excluded: several production kernels leave unused
  // partials, while paired kernels keep their private partials in local memory.
  uint32_t zero=0;e.upload(0,status,0,&zero,4);std::set<Allocation>checks;
  for(auto&[name,s]:e.buffers[0])checks.insert(s.id);for(auto&[name,id]:e.state_spares)checks.insert(id);
  for(auto src:checks)for(unsigned r=1;r<3;++r){Compare op;op.bytes=e.dev(0).arena.row(src).bytes;std::array ids{maps[0].at(src),maps[r].at(src),status};e.tail=e.dev(0).compute(op,ids,{});}e.drain();auto value=e.readback(0,status,4);uint32_t different;std::memcpy(&different,value.data(),4);
  auto emit=[&](const Timing&t){log<<"{\"wall_ms\":"<<t.wall<<",\"device_span_ms\":"<<t.span<<",\"device_sum_ms\":"<<t.sum<<",\"classes_ms\":{";bool comma=false;for(auto&[name,ms]:t.classes){log<<(comma?",":"")<<ownrt::quote(name)<<":"<<ms;comma=true;}log<<"}}";};
  log<<"{\"schema\":\"packet68b.sample.v1\",\"rank\":"<<e.a.rank<<",\"request_directory\":"<<ownrt::quote(e.a.output.string())<<",\"fixture\":"<<fixture<<",\"position\":"<<position<<",\"order\":"<<ownrt::quote(reverse?"H2,H1":"H1,H2")<<",\"row_kind\":\"duplicate-independent-state\",\"clone_bytes\":"<<clone_bytes<<",\"copy_ms\":"<<copy_ms<<",\"byte_identity\":"<<(different?"false":"true")<<",\"H1\":";emit(h1);log<<",\"H2\":";emit(h2);log<<",\"batched_classes\":[";bool comma=false;for(auto&name:batched){log<<(comma?",":"")<<ownrt::quote(name);comma=true;}log<<"],\"serial_classes\":[";comma=false;for(auto&name:serial){log<<(comma?",":"")<<ownrt::quote(name);comma=true;}log<<"]}\n";log.flush();require(!different,"68b paired row/state bytes differ from production M1");
 }
};
}
