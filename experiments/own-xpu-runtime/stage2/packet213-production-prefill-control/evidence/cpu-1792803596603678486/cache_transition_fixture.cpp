// Real CPU cache/copy/arena paths; completion markers remain the inherited Host simulation.
#include "../packet205-host-row-capture/host_backend.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/cache_table.hpp"
#include "cache_transition.hpp"
#include <array>
#include <iostream>
#include <map>
using namespace ownrt;
namespace {
void need(bool v,const char*why){if(!v)throw std::runtime_error(why);}
template<class F>bool refuses(F f){try{f();return false;}catch(const std::exception&){return true;}}
using Phase=p213::CacheTransition::Phase;
struct Touch final:integrated::HostOperation{void run(std::span<void*const> p)const override{need(p.size()==2&&p[0]&&p[1],"retained host endpoints");}};
struct Fixture{
 Host*host;Device device;Allocation payload,arena,table,staging;size_t offset=0;std::unique_ptr<p58::Cache>cache;p213::CacheTransition transition;std::vector<Event>events;bool closed=false;
 Fixture():host(new Host),device(std::unique_ptr<Backend>(host)){
  payload=alloc("payload",192,Memory::pinned);arena=alloc("arena",512+255,Memory::device);table=alloc("table",2*sizeof(p58::Entry),Memory::device);staging=alloc("staging",2*sizeof(p58::Entry),Memory::pinned);
  for(unsigned i=0;i<192;++i)static_cast<unsigned char*>(ptr(payload))[i]=static_cast<unsigned char>(i*17+3);
  auto base=uintptr_t(ptr(arena));offset=((base+255)&~uintptr_t(255))-base;std::vector<p58::Expert> experts;
  for(unsigned i=0;i<2;++i){auto p=uint64_t(ptr(payload))+i*96;experts.push_back({p,p+32,p+64,32,32,32});}
  cache=std::make_unique<p58::Cache>(experts,base+offset,512);publish(cache->table());drain();
 }
 ~Fixture(){if(!closed){auto r=device.shutdown(std::chrono::milliseconds(100));if(!r.safe_to_exit){std::cerr<<"retained fixture cleanup: "<<r.json()<<'\n';std::abort();}}}
 Allocation alloc(const char*name,size_t n,Memory memory){auto id=device.arena.allocate(std::string("p213:")+name,n,memory,memory==Memory::pinned?Category::pinned_slab:Category::scratch,memory==Memory::pinned?Lifetime::transfer:Lifetime::transaction);std::memset(device.arena.row(id).pointer,0,n);return id;}
 void*ptr(Allocation id){return device.arena.row(id).pointer;}
 void drain(){for(auto e:events)need(device.wait(e,std::chrono::milliseconds(100))&&device.complete(e),"Host marker pending");need(device.in_flight()==0,"Host inflight");device.retire_completed_events();events.clear();}
 bool drained(){return events.empty()&&device.in_flight()==0;}
 void ready(){auto epoch=transition.begin(*cache);transition.finish(*cache,epoch,drained());need(transition.phase()==Phase::ready,"actual ready transition");}
 void fill(const p58::Plan&p){CopyEngine copy(device);for(auto f:p.fills)for(unsigned projection=0;projection<3;++projection)events.push_back(copy.copy(arena,offset+f.offset+projection*32,payload,f.expert*96+projection*32,32,{}));drain();}
 void publish(const std::vector<p58::Entry>&entries){need(drained(),"publication staging busy");std::memcpy(ptr(staging),entries.data(),entries.size()*sizeof(p58::Entry));CopyEngine copy(device);events.push_back(copy.copy(table,0,staging,0,2*sizeof(p58::Entry),{}));}
 void update(){auto p=transition.prepare(*cache,{0,1});fill(p);publish(p.table);drain();transition.commit(*cache,p.epoch,true,true);}
 Receipt finish(){need(drained(),"fixture close requires actual drain");need(transition.close(*cache,true),"cache close failed");auto r=device.shutdown(std::chrono::milliseconds(100));need(r.safe_to_exit&&r.in_flight==0,"owner not safe");closed=true;return r;}
};
}
int main(){try{
 std::map<std::string,bool>checks;std::map<std::string,std::string>receipts,errors;auto pass=[&](std::string n,bool v){need(v,n.c_str());checks[n]=true;};
 static_assert(std::is_nothrow_move_constructible_v<p58::Plan>);static_assert(std::is_nothrow_move_assignable_v<p58::Plan>);
 {
  Fixture f;f.ready();f.update();pass("actual_fill_bytes_exact",std::memcmp(static_cast<unsigned char*>(f.ptr(f.arena))+f.offset,f.ptr(f.payload),96)==0&&std::memcmp(static_cast<unsigned char*>(f.ptr(f.arena))+f.offset+256,static_cast<unsigned char*>(f.ptr(f.payload))+96,96)==0);
  pass("actual_table_publication_exact",std::memcmp(f.ptr(f.table),f.cache->table().data(),2*sizeof(p58::Entry))==0);
  pass("successful_commit_tracks_idle",f.transition.phase()==Phase::idle&&f.cache->resident(0)&&f.cache->resident(1));auto first_epoch=f.transition.epoch();f.ready();auto ordinary_epoch=f.transition.epoch();f.update();f.ready();auto next_chunk_epoch=f.transition.epoch();f.update();pass("chunk_tail_next_chunk_epochs_advance",first_epoch+1==ordinary_epoch&&ordinary_epoch+1==next_chunk_epoch&&f.transition.phase()==Phase::idle);receipts["success"]=f.finish().json();pass("only_success_case_successful_close",f.transition.successful_close());
 }
 for(unsigned scenario=0;scenario<5;++scenario){Fixture f;f.ready();std::string name;Phase expected=Phase::ready;std::exception_ptr original;
  try{
   if(scenario==0){name="before_prepare";throw std::runtime_error("injected before prepare");}
   if(scenario==1){name="prepare_refusal";f.transition.prepare(*f.cache,{2});throw std::runtime_error("missing actual prepare refusal");}
   auto p=f.transition.prepare(*f.cache,{0,1});expected=Phase::updating;
   if(scenario==2){name="prepared_copy_failure";CopyEngine copy(f.device);copy.copy(f.arena,f.offset,f.payload,0,193,{});throw std::runtime_error("missing actual copy refusal");}
   f.fill(p);f.publish(p.table);f.drain();
   if(scenario==3){name="publication_commit_refusal";f.transition.commit(*f.cache,p.epoch,true,false);throw std::runtime_error("missing actual commit refusal");}
   f.transition.commit(*f.cache,p.epoch,true,true);expected=Phase::idle;name="postcommit_stats_failure";throw std::runtime_error("injected stats save failure");
  }catch(const std::exception&e){original=std::current_exception();errors[name]=e.what();if(scenario==1||scenario==3)pass(name+"_wrapper_autopoison_before_caller",f.transition.poisoned()&&f.transition.failure()==original);f.transition.poison(original);}
  pass(name+"_phase_tracks_actual_cache",f.transition.phase()==expected);
  pass(name+"_first_error_retained",f.transition.failure()==original&&original!=nullptr);
  try{throw std::runtime_error("secondary cleanup observation");}catch(...){f.transition.poison();}
  pass(name+"_secondary_does_not_replace",f.transition.failure()==original);
  pass(name+"_poison_intake_closed",refuses([&]{f.transition.begin(*f.cache);})&&refuses([&]{f.transition.prepare(*f.cache,{0});}));
  auto before=f.transition.phase();pass(name+"_incomplete_drain_no_transition",!f.transition.close(*f.cache,false)&&f.transition.phase()==before&&f.device.arena.row(f.payload).live&&f.device.arena.row(f.table).live);
  f.drain();receipts[name]=f.finish().json();pass(name+"_closed_without_success",f.transition.phase()==Phase::closed&&f.transition.poisoned()&&!f.transition.successful_close()&&f.transition.failure()==original);
  pass(name+"_closed_cache_refuses_access",refuses([&]{f.cache->table();}));
 }
 pass("actual_prepare_error",errors["prepare_refusal"]=="route outside expert table");pass("actual_copy_error",errors["prepared_copy_failure"]=="copy extent/lifetime");pass("actual_commit_error",errors["publication_commit_refusal"]=="new device table has not passed its publication fence");
 {
  Fixture f;f.ready();auto p=f.transition.prepare(*f.cache,{0});f.fill(p);f.host->auto_marker=false;Touch op;std::array<Allocation,2> ids{f.arena,f.table};f.events.push_back(f.device.compute(op,ids,{}));
  try{throw std::runtime_error("injected pending publication failure");}catch(...){f.transition.poison();}auto error=f.transition.failure();
  pass("pending_marker_actual_owner_inflight",f.device.in_flight()>0);
  pass("pending_marker_close_retains_phase",!f.transition.close(*f.cache,f.drained())&&f.transition.phase()==Phase::updating);
  pass("pending_marker_payload_and_table_release_refused",refuses([&]{f.device.arena.release(f.payload);})&&refuses([&]{f.device.arena.release(f.table);}));
  pass("pending_marker_both_allocations_live",f.device.arena.row(f.payload).live&&f.device.arena.row(f.table).live);
  f.host->finish_all();f.host->auto_marker=true;f.drain();receipts["pending_marker"]=f.finish().json();pass("pending_marker_completed_cleanup_preserves_failure",f.transition.failure()==error&&f.transition.poisoned()&&!f.transition.successful_close());
 }

 {
  Fixture f;f.ready();auto p=f.transition.prepare(*f.cache,{0});std::vector<unsigned char> before(static_cast<unsigned char*>(f.ptr(f.arena)),static_cast<unsigned char*>(f.ptr(f.arena))+f.device.arena.row(f.arena).bytes);std::array<p58::Entry,2> old_table;std::memcpy(old_table.data(),f.ptr(f.table),sizeof(old_table));
  std::exception_ptr error;try{CopyEngine copy(f.device);f.events.push_back(copy.copy(f.arena,f.offset,f.payload,0,32,{}));copy.copy(f.arena,f.offset+32,f.payload,32,193,{});}catch(const std::exception&e){error=std::current_exception();errors["partial_fill"]=e.what();f.transition.poison(error);}
  pass("partial_fill_first_error_exact",error&&errors["partial_fill"]=="copy extent/lifetime"&&f.transition.failure()==error);
  auto* bytes=static_cast<unsigned char*>(f.ptr(f.arena));pass("partial_fill_first_projection_changed",std::memcmp(bytes+f.offset,before.data()+f.offset,32)!=0&&std::memcmp(bytes+f.offset,f.ptr(f.payload),32)==0);
  pass("partial_fill_remaining_and_old_table_unchanged",std::memcmp(bytes+f.offset+32,before.data()+f.offset+32,64)==0&&std::memcmp(f.ptr(f.table),old_table.data(),sizeof(old_table))==0);
  pass("partial_fill_no_rollback_or_new_intake",f.transition.phase()==Phase::updating&&f.transition.poisoned()&&refuses([&]{f.transition.begin(*f.cache);})&&refuses([&]{f.transition.prepare(*f.cache,{1});}));
  f.drain();receipts["partial_fill"]=f.finish().json();pass("partial_fill_failed_close_safe_not_success",f.transition.phase()==Phase::closed&&!f.transition.successful_close()&&f.transition.failure()==error);
 }
 for(unsigned variant=0;variant<2;++variant){Fixture f;auto epoch=f.transition.begin(*f.cache);std::string name=variant?"readers_finish_refusal":"readers_external_failure";std::exception_ptr error;
  try{if(variant)f.transition.finish(*f.cache,epoch,false);else throw std::runtime_error("injected readers failure");}catch(const std::exception&e){error=std::current_exception();errors[name]=e.what();if(variant)pass(name+"_automatic_poison",f.transition.poisoned()&&f.transition.failure()==error);f.transition.poison(error);}
  pass(name+"_phase_retained",f.transition.phase()==Phase::readers&&f.transition.poisoned()&&error);
  pass(name+"_incomplete_close_retains",!f.transition.close(*f.cache,false)&&f.transition.phase()==Phase::readers&&f.device.arena.row(f.payload).live&&f.device.arena.row(f.table).live);
  f.drain();receipts[name]=f.finish().json();pass(name+"_drained_close_without_success",f.transition.phase()==Phase::closed&&f.transition.failure()==error&&!f.transition.successful_close()&&refuses([&]{f.transition.begin(*f.cache);}));
 }
 pass("actual_finish_refusal_error",errors["readers_finish_refusal"]=="compute still owns cache slots/pinned sources");
 std::cout<<"{\"schema\":\"packet213.cache-transition-proof.v1\",\"passed\":true,\"device_executed\":false,\"model_executed\":false,\"completion_scope\":\"real CPU copies and actual Cache; inherited Host simulated completion markers\",\"checks\":{";bool first=true;for(auto&[n,v]:checks){std::cout<<(first?"":",")<<quote(n)<<":true";first=false;}std::cout<<"},\"first_errors\":{";first=true;for(auto&[n,v]:errors){std::cout<<(first?"":",")<<quote(n)<<':'<<quote(v);first=false;}std::cout<<"},\"owner_receipts\":{";first=true;for(auto&[n,v]:receipts){std::cout<<(first?"":",")<<quote(n)<<':'<<v;first=false;}std::cout<<"}}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
