#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/batched_experts.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/production_rows.hpp"
namespace p151s {
using p68c::experts;using p68c::production_dense;using iq3::Type;
using Commands=std::vector<ownrt::PreparedCompute>;using Schedule=std::vector<Commands>;
using Map=std::map<Allocation,Allocation>;
struct RowScope {
 Engine&e;decltype(e.buffers) buffers;decltype(e.prepared) prepared;decltype(e.matrices) matrices;
 decltype(e.state_spares) spares;std::vector<Allocation>scratch,workspace,controls,scores,probabilities,mixture,fp32,sources;std::vector<size_t>extents;
 RowScope(Engine&v,const Map&m):e(v),buffers(e.buffers),prepared(std::move(e.prepared)),matrices(std::move(e.matrices)),spares(e.state_spares),scratch(e.scratch),workspace(e.workspace),controls(e.controls),scores(e.scores),probabilities(e.probabilities),mixture(e.mixture_out),fp32(e.fp32_inputs),sources(e.fp32_sources),extents(e.fp32_extents){
  auto remap=[&](auto&ids){for(auto&id:ids)id=m.at(id);};for(auto&[name,s]:e.buffers[0])s.id=m.at(s.id);for(auto&[name,id]:e.state_spares)id=m.at(id);
  remap(e.scratch);remap(e.workspace);remap(e.controls);remap(e.scores);remap(e.probabilities);remap(e.mixture_out);remap(e.fp32_inputs);std::fill(e.fp32_sources.begin(),e.fp32_sources.end(),0);e.prepared.clear();e.matrices.clear();e.prepare_plan();
 }
 ~RowScope(){e.buffers=std::move(buffers);e.prepared=std::move(prepared);e.matrices=std::move(matrices);e.state_spares=std::move(spares);e.scratch=scratch;e.workspace=workspace;e.controls=controls;e.scores=scores;e.probabilities=probabilities;e.mixture_out=mixture;e.fp32_inputs=fp32;e.fp32_sources=sources;e.fp32_extents=extents;}
};

struct Sibling {
 Engine&e;std::array<Map,3>maps;std::map<Allocation,size_t>sizes;
 std::map<std::tuple<int,int,int>,Schedule> caches;Schedule*current=nullptr;
 size_t bytes=0,paired_sites=0,serial_sites=0;int alternate=-1;
 explicit Sibling(Engine&v):e(v){
  require(e.a.rank==0&&e.resident&&e.prepared_path,"sibling rank0 resident ownership");
  std::set<Allocation>ids;for(auto&[name,b]:e.buffers[0])ids.insert(b.id);
  for(auto&[name,id]:e.state_spares)ids.insert(id);for(auto&[name,id]:e.state_reserves)ids.insert(id);
  for(auto list:{e.scratch,e.workspace,e.controls,e.scores,e.probabilities,e.mixture_out,e.fp32_inputs})for(auto id:list)ids.insert(id);
  for(auto id:ids){auto&r=e.dev(0).arena.row(id);size_t n=r.bytes;
   if(id==e.scratch[0])n=std::min(n,std::max(size_t(8*1024*1024),pipeline::SnapshotWriteSet::scratch(e.p,n,true)));
   bytes+=n;sizes[id]=n;maps[1][id]=id;
  }
  require(bytes<=256ull*1024*1024,"sibling scratch exceeds preregistered 256 MiB");
  for(auto[id,n]:sizes){auto label=e.dev(0).arena.row(id).label;auto copy=e.allocate(0,"p151-sibling:"+label,n,Category::runtime_overhead,Lifetime::process);maps[2][id]=copy;e.probe_auxiliary.insert(copy);}
 }
 integrated::Matrix mapped(const flash::Launch&l,unsigned row,size_t projection=0){auto m=e.matrices.at(&l).at(projection);m.x=maps[row].at(m.x);m.y=maps[row].at(m.y);m.workspace=maps[row].at(m.workspace);if(m.routes)m.routes=maps[row].at(m.routes);if(m.status)m.status=maps[row].at(m.status);return m;}
 p60::IDs hc_ids(const flash::Launch&l,unsigned row){
  const std::string tag=l.label.substr(0,l.label.rfind('.')),prefix=tag.substr(0,tag.find(".hc.")),wt=prefix+(tag.ends_with(".a")?".hc_attn_":".hc_ffn_");
  auto id=[&](const std::string&n){return maps[row].at(e.buffers[0].at(n).id);};auto w=[&](const std::string&n){return e.weights[0].at(wt+n+".weight");};
  return {id("streams"),w("norm"),w("down"),w("up"),w("inject"),id(tag+".norm"),id(tag+".low"),id(tag+".act"),id(tag+".gate"),id(tag+".mix"),id(tag+".inject"),maps[row].at(e.scratch[0]),maps[row].at(e.workspace[0]),id("error"),id("active"),id("position")};
 }
 bool paired_site(const flash::Launch&l){
  // First sealed probe: production HC and small tuples remain serial M=1.
  int stage=p60::stage(l.label);if(stage>=0)return false;
  if(packet26::Dispatch::class_name(l.label)=="shexpdown")return false;
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

 void begin(int token){
  e.drain();alternate=(token+1)%e.p.g.vocab;
  ownrt::CopyEngine copy(e.dev(0));
  for(auto[id,n]:sizes)e.tail=copy.copy(maps[2].at(id),0,id,0,n,{});e.drain();
  auto key=std::make_tuple(e.active_bank,e.spare_bank,e.context_extent);
  Schedule right;
  {
   const auto h0=e.history0,h1=e.history1;auto lookups=e.lookup_ids;
   RowScope scope(e,maps[2]);e.put(0,"token",&alternate,4);e.prepare_token(alternate);
   e.history0=h0;e.history1=h1;e.lookup_ids=std::move(lookups);
   if(!caches.contains(key)){
    right.resize(e.p.launches.size());
    for(size_t i=0;i<right.size();++i){e.preparing_commands=true;e.dev(0).begin_capture(right[i]);
     try{e.execute_site(e.p.launches[i]);e.dev(0).end_capture();e.preparing_commands=false;}
     catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}
    }
   }
  }
  if(!caches.contains(key)){
   Schedule combined(e.p.launches.size());paired_sites=serial_sites=0;
   for(size_t i=0;i<combined.size();++i){e.preparing_commands=true;e.dev(0).begin_capture(combined[i]);bool pair=false;
    try{pair=paired_site(e.p.launches[i]);e.dev(0).end_capture();e.preparing_commands=false;}
    catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}
    if(pair)++paired_sites;else{combined[i]=e.issue_sites[i].commands;combined[i].insert(combined[i].end(),right[i].begin(),right[i].end());if(!right[i].empty())++serial_sites;}
   }
   require(paired_sites>0||e.a.mini,"no M2 shared-weight sites");caches.emplace(key,std::move(combined));
  }
  current=&caches.at(key);
 }
 void enqueue(const flash::Launch&l){
  require(current,"sibling not prepared");auto i=size_t(&l-e.p.launches.data());auto&cmd=e.issue_sites.at(i).commands;
  cmd.swap(current->at(i));try{e.enqueue(l,e.logical);cmd.swap(current->at(i));}catch(...){cmd.swap(current->at(i));throw;}
 }
};
}
