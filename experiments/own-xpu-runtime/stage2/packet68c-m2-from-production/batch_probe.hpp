#pragma once
#include "batched_hc.hpp"
#include "batched_experts.hpp"
#include "production_rows.hpp"
namespace p68c {
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
  require(clone_bytes+4<=512ull*1024*1024,"68c clone budget exceeds 512 MiB per rank");
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
  // First sealed probe: production HC and small tuples remain serial M=1.
  int stage=p60::stage(l.label);if(stage>=0)return false;
  if(e.small_followers.count(&l))return false;
  if(p49b_site(e.w,e.a,l)){
   std::vector<integrated::Matrix>a{mapped(l,1)},b{mapped(l,2)};
   if(l.op=="expert_gate_up"){a.push_back(mapped(l,1,1));b.push_back(mapped(l,2,1));}
   std::array<Allocation,2>error{maps[1].at(e.buffers[0].at("error").id),maps[2].at(e.buffers[0].at("error").id)},active{maps[1].at(e.buffers[0].at("active").id),maps[2].at(e.buffers[0].at("active").id)};
   experts(e.dev(0),a,b,error,active);return true;
  }
  if(l.op!="gemv")return false;
  bool attention=p39::tagged(l)&&p39::kind(l)==p39::Kind::attention_combine;
  if(p39::tagged(l)&&!attention)return false;
  if(e.small_groups.count(&l))return false;
  if(!attention&&e.gemv_choices.at(&l).first!="p33.dense.segment")return false;
  auto ma=mapped(l,1),mb=mapped(l,2);
  if(!attention&&!((ma.type==Type::Q6_K&&ma.columns==2560)||(ma.type==Type::Q8_0&&(ma.columns==2560||ma.columns==640||ma.columns==320))||(ma.type==Type::F32&&ma.columns==10240)))return false;
  auto cls=packet26::Dispatch::class_name(l.label),prefix=l.label.substr(0,l.label.size()-cls.size());
  auto id=[&](unsigned row,const std::string&n){return maps[row].at(e.buffers[0].at(n).id);};
  std::array<Allocation,8>tail{attention?id(1,"streams"):ma.y,attention?id(2,"streams"):mb.y,attention?id(1,prefix+"hc.a.inject"):ma.x,attention?id(2,prefix+"hc.a.inject"):mb.x,id(1,"error"),id(2,"error"),id(1,"active"),id(2,"active")};
  production_dense(e.dev(0),ma,mb,e.variant(l),attention,tail);return true;

 }
 struct Timing {double wall=0,span=0,sum=0;std::map<std::string,double>classes;};
 Timing replay(const Schedule&schedule){
  Timing t;std::vector<std::pair<ownrt::Event,size_t>>events;auto started=std::chrono::steady_clock::now();
  for(size_t i=0;i<schedule.size();++i){for(auto&cmd:schedule[i]){auto event=e.dev(0).issue(cmd);e.tail=event;events.emplace_back(event,i);}pipeline_cancel_check();}
  if(e.tail)e.wait(0,e.tail);t.wall=Engine::ms(started);
#ifndef OWN_RT_HOST_ONLY
  uint64_t first=0,last=0;for(auto[event,i]:events){auto time=e.dev(0).timing(event);require(time.start_ns&&time.end_ns>=time.start_ns&&time.end_ns-time.start_ns<4000000000ull,"68c event bound");if(!first)first=time.start_ns;last=time.end_ns;double ms=(time.end_ns-time.start_ns)/1e6;t.sum+=ms;t.classes[packet26::Dispatch::class_name(e.p.launches[i].label)]+=ms;}t.span=(last-first)/1e6;
#endif
  e.tail=0;e.dev(0).retire_completed_events();return t;
 }

 int saved_position=-1,saved_fixture=-1;std::map<std::string,Allocation> saved_buffers,saved_spares;
 void boundary(){
  if(e.tail)e.wait(0,e.tail);if(e.progress_pending&&e.progress_callback)e.progress_callback();require(!e.progress_pending,"68c outstanding draft publication");e.drain();
 }
 void copy_map(const Map&dest,const Map*source=nullptr){
  ownrt::CopyEngine copy(e.dev(0));
  for(auto[src,dst]:dest){size_t bytes=clone_sizes.at(src);auto from=source?source->at(src):src;
   for(size_t off=0;off<bytes;off+=64*1024*1024)e.tail=copy.copy(dst,off,from,off,std::min(size_t(64*1024*1024),bytes-off),{});
  }e.drain();
 }
 void save_previous(int fixture,int position){
  boundary();copy_map(maps[1]);saved_position=position;saved_fixture=fixture;
  saved_buffers.clear();for(auto&[name,b]:e.buffers[0])saved_buffers[name]=b.id;saved_spares=e.state_spares;
 }
 bool compare_row(unsigned row){
  uint32_t zero=0;e.upload(0,status,0,&zero,4);std::set<Allocation>checks;
  for(auto&[name,b]:e.buffers[0])checks.insert(b.id);for(auto&[name,id]:e.state_spares)checks.insert(id);
  for(auto src:checks){Compare op;op.bytes=e.dev(0).arena.row(src).bytes;std::array ids{maps[0].at(src),maps[row].at(src),status};e.tail=e.dev(0).compute(op,ids,{});}e.drain();auto value=e.readback(0,status,4);uint32_t different;std::memcpy(&different,value.data(),4);return !different;
 }
 struct Routes {unsigned sites=0,differing=0,shared=0,total=0;};
 Routes route_overlap(){
  Routes out;
  for(auto&l:e.p.launches)if(l.op=="expert_gate_up"&&p49b_site(e.w,e.a,l)){
   auto a=mapped(l,1),b=mapped(l,2);auto av=e.readback(0,a.routes,a.count*sizeof(iq3::Route)),bv=e.readback(0,b.routes,b.count*sizeof(iq3::Route));
   std::array<iq3::Route,10>ar{},br{};std::memcpy(ar.data(),av.data(),av.size());std::memcpy(br.data(),bv.data(),bv.size());
   unsigned common=0;for(unsigned i=0;i<a.count;++i)common+=matching_slot(ar.data(),br.data(),i,a.count)>=0;
   ++out.sites;out.shared+=common;out.total+=2*a.count-common;out.differing+=common<a.count;
  }return out;
 }
 static Timing average(const Timing&a,const Timing&b){Timing c;c.wall=(a.wall+b.wall)/2;c.span=(a.span+b.span)/2;c.sum=(a.sum+b.sum)/2;for(auto&[name,ms]:a.classes)c.classes[name]=(ms+b.classes.at(name))/2;return c;}
 void run(int fixture,int position,bool consecutive=false){
  boundary();
  if(consecutive){
   // A request may re-enter the same generated position after a miss. Preserve
   // the saved prior real input; require adjacent positions in this request.
   if(saved_position+1!=position||saved_fixture+1!=fixture)return;
   auto old=maps[1];
   for(auto&[name,b]:e.buffers[0])maps[1][b.id]=old.at(saved_buffers.at(name));
   for(auto&[name,id]:e.state_spares)maps[1][id]=old.at(saved_spares.at(name));
   saved_buffers.clear();for(auto&[name,b]:e.buffers[0])saved_buffers[name]=b.id;saved_spares=e.state_spares;
  }
  auto copy_start=std::chrono::steady_clock::now();
  if(consecutive){copy_map(maps[0],&maps[1]);copy_map(maps[2]);}
  else for(auto&m:maps)copy_map(m);
  double copy_ms=Engine::ms(copy_start);
  auto one=ordinary(0),left=ordinary(1),right=ordinary(2);Schedule two(one.size());std::set<std::string>batched,serial;
  for(size_t i=0;i<two.size();++i){e.preparing_commands=true;e.dev(0).begin_capture(two[i]);bool paired=false;
   try{paired=paired_site(e.p.launches[i]);e.dev(0).end_capture();e.preparing_commands=false;}catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}
   auto name=packet26::Dispatch::class_name(e.p.launches[i].label);
   if(paired)batched.insert(name);else {two[i]=left[i];two[i].insert(two[i].end(),right[i].begin(),right[i].end());serial.insert(name);}
  }
  Timing first,second,h1,h2;bool reverse=sample++%2;
  if(reverse){h2=replay(two);first=replay(one);}else{first=replay(one);h2=replay(two);}
  bool exact0=compare_row(1),exact1=false;auto routes=route_overlap();
  if(consecutive){
   copy_start=std::chrono::steady_clock::now();copy_map(maps[0]);copy_ms+=Engine::ms(copy_start);
   second=replay(one);exact1=compare_row(2);h1=average(first,second);
  }else{second=first;h1=first;exact1=compare_row(2);}
  auto emit=[&](const Timing&t){log<<"{\"wall_ms\":"<<t.wall<<",\"device_span_ms\":"<<t.span<<",\"device_sum_ms\":"<<t.sum<<",\"classes_ms\":{";bool comma=false;for(auto&[name,ms]:t.classes){log<<(comma?",":"")<<ownrt::quote(name)<<":"<<ms;comma=true;}log<<"}}";};
  log<<"{\"schema\":\"packet68c.sample.v1\",\"rank\":"<<e.a.rank<<",\"request_directory\":"<<ownrt::quote(e.a.output.string())<<",\"fixture\":"<<fixture<<",\"position\":"<<position<<",\"previous_position\":"<<(consecutive?saved_position:position)<<",\"order\":"<<ownrt::quote(reverse?"H2,H1":"H1,H2")<<",\"row_kind\":"<<ownrt::quote(consecutive?"consecutive-engine-inputs-independent-state":"duplicate-independent-state")<<",\"clone_bytes\":"<<clone_bytes<<",\"copy_ms\":"<<copy_ms<<",\"byte_identity\":"<<(exact0&&exact1?"true":"false")<<",\"row_identity\":["<<(exact0?"true":"false")<<","<<(exact1?"true":"false")<<"],\"route_sites\":"<<routes.sites<<",\"differing_route_sites\":"<<routes.differing<<",\"shared_experts\":"<<routes.shared<<",\"union_experts\":"<<routes.total<<",\"H1\":";
  emit(h1);log<<",\"H1_rows\":[";emit(first);log<<",";emit(second);log<<"],\"H2\":";emit(h2);
  log<<",\"batched_classes\":[";bool comma=false;for(auto&name:batched){log<<(comma?",":"")<<ownrt::quote(name);comma=true;}
  log<<"],\"serial_classes\":[";comma=false;for(auto&name:serial){log<<(comma?",":"")<<ownrt::quote(name);comma=true;}log<<"]}\n";log.flush();
  require(exact0&&exact1,"68c paired row/state bytes differ from production M1");
  if(!consecutive)save_previous(fixture,position);
  else saved_position=-1; // never reuse an already executed candidate image
 }
};
}
