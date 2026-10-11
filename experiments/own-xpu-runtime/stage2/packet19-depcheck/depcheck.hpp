#pragma once
// CPU-only DAG/range ownership checker. No accelerator headers or discovery.
#include "../../stage1/packet3-prep/src/owner.hpp"
#include <algorithm>
#include <cstring>
#include <fstream>
#include <random>
#include <set>
#include <sstream>
#include <cstdlib>
namespace depcheck {
using ownrt::Event;
struct Access { void* p; size_t bytes; bool read,write,index=false; };
struct Segment {size_t end; bool initialized=false; Event writer=0; std::set<Event> readers;};
struct Allocation {size_t bytes; int device,context; std::string name; bool live=true; std::map<size_t,Segment> segments;};
struct Work {std::string site;int queue;std::vector<Event> deps;std::vector<uint64_t> ancestors;std::vector<Access> access;std::function<void()> run;bool done=false,visible=false;size_t index;bool unsafe=false;};
class Checker {
 public:
 std::map<uintptr_t,Allocation> allocations;
 std::map<Event,Work> work;
 std::vector<std::string> violations;
 std::ofstream trace;
 bool strict=false,randomized=true;std::mt19937_64 random{1};size_t submitted=0,executed=0,max_ready=0;
 std::string site="initialization";
 void fail(const std::string& kind,const Allocation& a,Event needed=0) {
  std::string v=site+": "+kind+" allocation="+a.name;
  if(needed)v+=" missing edge from event="+std::to_string(needed)+" ("+work.at(needed).site+")";
  violations.push_back(v);if(strict)throw std::logic_error(v);
 }
 auto locate(void* p,size_t n) {
  auto addr=reinterpret_cast<uintptr_t>(p);auto it=allocations.upper_bound(addr);
  if(it==allocations.begin())throw std::logic_error("unknown pointer");--it;
  if(addr-it->first>it->second.bytes||n>it->second.bytes-(addr-it->first))throw std::logic_error("out-of-range access");
  return it;
 }
 void add(void* p,size_t bytes,int device,int context,std::string name) {
  auto key=reinterpret_cast<uintptr_t>(p);
  if(!p||!bytes||bytes>UINTPTR_MAX-key)throw std::logic_error("invalid allocation extent");
  for(auto it=allocations.begin();it!=allocations.end();){
   const auto base=it->first;const auto end=base+it->second.bytes;
   if(key<end&&base<key+bytes){if(it->second.live)throw std::logic_error("overlapping allocation");it=allocations.erase(it);}else ++it;
  }
  allocations[key]={bytes,device,context,std::move(name),true,{{0,{bytes,false,0,{}}}}};
 }
 static void split(Allocation& a,size_t at) {
  if(!at||at==a.bytes)return;auto it=std::prev(a.segments.upper_bound(at));if(it->first==at)return;
  auto s=it->second;it->second.end=at;a.segments.emplace(at,std::move(s));
 }
 bool ordered(const Work& now,Event before) const {
  if(!before)return true;const auto& w=work.at(before);if(w.visible)return true;
  return w.index/64<now.ancestors.size()&&(now.ancestors[w.index/64]&(uint64_t(1)<<(w.index%64)));
 }
 void host_write(void* p,size_t n) {
  auto it=locate(p,n);auto& a=it->second;if(!a.live){fail("host use-after-release",a);throw std::logic_error("refusing host write to released memory");}
  size_t off=reinterpret_cast<uintptr_t>(p)-it->first;split(a,off);split(a,off+n);
  for(auto s=a.segments.lower_bound(off);s!=a.segments.end()&&s->first<off+n;++s){
   auto& v=s->second;
   if(v.writer&&!work.at(v.writer).visible)fail("host WAW",a,v.writer);
   for(auto e:v.readers)if(!work.at(e).visible)fail("host WAR",a,e);
   v.initialized=true;v.writer=0;v.readers.clear();
  }
 }
 Event submit(int queue,int context,std::vector<Access> accesses,std::span<const Event> deps,std::function<void()> run,bool peer=false) {
  Event e=ownrt::next_handle();Work w{site,queue,{deps.begin(),deps.end()},{},accesses,std::move(run),false,false,work.size()};
  w.ancestors.resize((w.index+63)/64);
  for(auto d:deps){const auto& parent=work.at(d);for(size_t j=0;j<parent.ancestors.size();++j)w.ancestors[j]|=parent.ancestors[j];w.ancestors[parent.index/64]|=uint64_t(1)<<(parent.index%64);}
  // Validate all accesses against pre-submission state: aliases inside one op
  // must not create fictitious self hazards. Then apply reads before writes.
  for(auto x:accesses){auto it=locate(x.p,x.bytes);auto& a=it->second;
   if(!a.live){fail("use-after-release",a);w.unsafe=true;}
   if(a.context!=context)fail("foreign context",a);
   if(a.device>=0&&a.device!=queue&&!peer)fail("cross-device binding",a);
   size_t off=reinterpret_cast<uintptr_t>(x.p)-it->first;split(a,off);split(a,off+x.bytes);
   for(auto s=a.segments.lower_bound(off);s!=a.segments.end()&&s->first<off+x.bytes;++s){auto& v=s->second;
    if(x.read){if(!v.initialized){fail(x.index?"uninitialized INDEX":"uninitialized read",a);w.unsafe=w.unsafe||x.index;}if(!ordered(w,v.writer))fail("RAW",a,v.writer);}
    if(x.write){if(!ordered(w,v.writer))fail("WAW",a,v.writer);for(auto r:v.readers)if(!ordered(w,r))fail("WAR",a,r);}
   }
  }
  for(bool write:{false,true})for(auto x:accesses)if(write?x.write:x.read){auto it=locate(x.p,x.bytes);auto& a=it->second;size_t off=reinterpret_cast<uintptr_t>(x.p)-it->first;
   for(auto s=a.segments.lower_bound(off);s!=a.segments.end()&&s->first<off+x.bytes;++s){auto& v=s->second;if(write){v.initialized=true;v.writer=e;v.readers.clear();}else v.readers.insert(e);}
  }
  if(trace){trace<<"{\"event\":"<<e<<",\"site\":"<<ownrt::quote(site)<<",\"queue\":"<<queue<<",\"context\":"<<context<<",\"peer\":"<<(peer?"true":"false")<<",\"deps\":[";
   for(size_t i=0;i<w.deps.size();++i)trace<<(i?",":"")<<w.deps[i];trace<<"],\"access\":[";
   for(size_t i=0;i<accesses.size();++i){auto x=accesses[i];auto a=locate(x.p,x.bytes);trace<<(i?",":"")<<"{\"name\":"<<ownrt::quote(a->second.name)<<",\"owner\":"<<a->second.device<<",\"context\":"<<a->second.context<<",\"offset\":"<<reinterpret_cast<uintptr_t>(x.p)-a->first<<",\"bytes\":"<<x.bytes<<",\"read\":"<<x.read<<",\"write\":"<<x.write<<",\"index\":"<<x.index<<"}";}
   trace<<"]}\n";
  }
  work.emplace(e,std::move(w));++submitted;return e;
 }
 // memcpy preserves poison: writing bytes copied from an uninitialized slab
 // must not turn them into initialized device indices. Snapshot before submit.
 Event copy_bytes(int queue,int context,void* dst,const void* src,size_t n,std::span<const Event> deps,bool peer=false){
  auto si=locate(const_cast<void*>(src),n),di=locate(dst,n);
  size_t so=reinterpret_cast<uintptr_t>(src)-si->first,off=reinterpret_cast<uintptr_t>(dst)-di->first;
  if(si==di&&so<off+n&&off<so+n)throw std::logic_error("overlapping memcpy ranges");
  struct Poison{size_t begin,end;bool initialized;};std::vector<Poison> poison;
  split(si->second,so);split(si->second,so+n);
  for(auto it=si->second.segments.lower_bound(so);it!=si->second.segments.end()&&it->first<so+n;++it)poison.push_back({it->first-so,it->second.end-so,it->second.initialized});
  auto e=submit(queue,context,{{const_cast<void*>(src),n,true,false},{dst,n,false,true}},deps,[=]{std::memcpy(dst,src,n);},peer);
  auto& dest=di->second;for(auto p:poison){split(dest,off+p.begin);split(dest,off+p.end);for(auto it=dest.segments.lower_bound(off+p.begin);it!=dest.segments.end()&&it->first<off+p.end;++it)it->second.initialized=p.initialized;}
  return e;
 }
 void execute_until(Event target=0) {
  while(!target||!work.at(target).done){std::vector<Event> ready;bool pending=false;
   for(auto& [e,w]:work)if(!w.done){pending=true;bool ok=true;for(auto d:w.deps)ok=ok&&work.at(d).done;if(ok)ready.push_back(e);}
   if(ready.empty()){if(pending)throw std::logic_error("dependency cycle");break;}
   max_ready=std::max(max_ready,ready.size());auto e=ready[randomized?random()%ready.size():0];auto& w=work.at(e);
   auto previous=site;site=w.site;
   if(w.unsafe)throw std::logic_error(site+": refusing unsafe indexed/lifetime execution");
   for(auto x:w.access)if(!locate(x.p,x.bytes)->second.live){fail("execution use-after-release",locate(x.p,x.bytes)->second);throw std::logic_error(site+": refusing released memory execution");}
   w.run();w.done=true;++executed;site=previous;
  }
 }
 void fence(Event e) {execute_until(e);auto& w=work.at(e);w.visible=true;for(auto& [id,p]:work)if(ordered(w,id))p.visible=true;}
 void sync(){execute_until();for(auto& [e,w]:work)w.visible=true;}
 void release(void* p) {auto& a=locate(p,1)->second;if(!a.live){fail("double release",a);throw std::logic_error("refusing double release");}
  auto base=locate(p,1)->first;if(base!=reinterpret_cast<uintptr_t>(p))throw std::logic_error("release requires allocation base");
  bool pending=false;for(auto& [e,w]:work)if(!w.done)for(auto x:w.access)if(locate(x.p,x.bytes)->first==base){fail("release while pending",a,e);pending=true;}
  if(pending)throw std::logic_error("release while pending: ownership retained");
  a.live=false;
 }
 void clear(){for(auto& [e,w]:work)if(!w.done||!w.visible)throw std::logic_error("event release before host fence");for(auto& [p,a]:allocations)for(auto& [off,s]:a.segments){s.writer=0;s.readers.clear();}work.clear();}
};
inline Checker checker;
inline int card=0;
inline std::function<void(std::span<void*const>)> closure;
inline std::vector<Access> accesses;
class Backend final:public ownrt::Backend {
 public:
 std::string identity()const override{return "Packet19 CPU dependency sanitizer";}
 void* allocate(size_t n,ownrt::Memory m)override{auto p=::operator new(n);checker.add(p,n,m==ownrt::Memory::device?card:-1,0,"unnamed");return p;}
 void release(void* p,ownrt::Memory)override{checker.release(p);::operator delete(p);}
 Event copy(void* dst,const void* src,size_t n,std::span<const Event> deps)override{
  auto d=checker.locate(dst,n)->second.device,s=checker.locate(const_cast<void*>(src),n)->second.device;
  return checker.copy_bytes(d>=0?d:s>=0?s:0,0,dst,src,n,deps,d>=0&&s>=0&&d!=s);
 }
 Event compute(const ownrt::Operation&,std::span<void*const> p,std::span<const Event> deps)override{
  for(auto ptr:p){auto& a=checker.locate(ptr,1)->second;if(!a.live)throw std::logic_error("compute binding use-after-release: "+a.name);if(a.context!=0)checker.fail("foreign context binding",a);if(a.device!=card)checker.fail("cross-device binding",a);}
  if(!closure)throw std::logic_error("uninstrumented operation");auto f=std::move(closure);closure={};std::vector<void*> b(p.begin(),p.end());
  return checker.submit(card,0,std::move(accesses),deps,[f,b]{f(b);});
 }
 Event marker(std::span<const Event> deps)override{return checker.submit(card,0,{},deps,[]{});}
 bool complete(Event e)override{return checker.work.at(e).done;}
 bool wait(Event e,ownrt::Deadline)override{checker.fence(e);return true;}
 void synchronize()override{checker.sync();}
 void clear_events()override{checker.clear();}
 void close_queue()override{if(!checker.work.empty())throw std::logic_error("queue with live events");for(auto& [p,a]:checker.allocations)if(a.live)throw std::logic_error("queue with live allocation");}
 void close_context()override{}
};
inline void setup(){if(auto s=getenv("DEPCHECK_SEED")){checker.random.seed(std::stoull(s));checker.randomized=std::string(s)!="0";}if(auto p=getenv("DEPCHECK_TRACE"))checker.trace.open(p);}
inline int report(int rc){if(auto p=getenv("DEPCHECK_REPORT")){std::ofstream f(p);f<<"{\"device_executed\":false,\"submissions\":"<<checker.submitted<<",\"executed\":"<<checker.executed<<",\"max_ready\":"<<checker.max_ready<<",\"violations\":[";for(size_t i=0;i<checker.violations.size();++i)f<<(i?",":"")<<ownrt::quote(checker.violations[i]);f<<"]}\n";}return rc?rc:checker.violations.empty()?0:2;}
}
