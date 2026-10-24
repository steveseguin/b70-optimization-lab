// Full production table extents; synthetic CPU pointers/payloads and Host markers only.
#include "../packet205-host-row-capture/host_backend.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/cache_table.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/publish.hpp"
#include "../packet213-production-prefill-control/cache_transition.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p58_pointer.hpp"
#include "publication.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#include <map>
#include <openssl/sha.h>
using namespace ownrt;
namespace {
constexpr size_t layers=48,experts=512,tables=144,entry_bytes=16,table_bytes=experts*entry_bytes,total_bytes=tables*table_bytes,bank_bytes=layers*experts*3*sizeof(uint64_t);
void need(bool v,const char*why){if(!v)throw std::runtime_error(why);}
template<class F>bool refuses(F f){try{f();return false;}catch(const std::exception&){return true;}}
using Pointer=p58::Pointer;static_assert(sizeof(Pointer)==entry_bytes);
uint64_t payload_value(unsigned generation,unsigned layer,unsigned projection,unsigned expert){return uint64_t(generation)*1000000007+layer*1000003+projection*10007+expert*31;}
std::string sha(const std::vector<unsigned char>&v){unsigned char out[32];SHA256(v.data(),v.size(),out);std::string s;for(auto b:out){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
struct Consumer final:integrated::HostOperation{
 void run(std::span<void*const> p)const override{need(p.size()==4,"consumer binding");auto*out=static_cast<uint64_t*>(p[3]);std::array<unsigned,3>slots{0,17,511};for(unsigned i=0;i<3;++i){auto e=static_cast<const Pointer*>(p[i])[slots[i]];need(e.address&&e.generation,"published entry");out[i*2]=*reinterpret_cast<const uint64_t*>(e.address);out[i*2+1]=e.generation;}}
};
struct Fixture{
 Host*host;Device device;std::array<Allocation,144>a{},b{},decoy{};Allocation stage_a,stage_b,upload_a,upload_b,bank1,bank2,out_a,out_b,cache_arena;size_t count=0;bool closed=false;
 std::array<std::vector<PreparedCompute>,2>consumers;std::vector<Event>events;
 Fixture():host(new Host),device(std::unique_ptr<Backend>(host)){
  stage_a=alloc("stage-a",total_bytes,Memory::pinned);stage_b=alloc("stage-b",total_bytes,Memory::pinned);upload_a=alloc("upload-a",total_bytes);upload_b=alloc("upload-b",total_bytes);bank1=alloc("payload1",bank_bytes,Memory::pinned);bank2=alloc("payload2",bank_bytes,Memory::pinned);out_a=alloc("out-a",6*sizeof(uint64_t));out_b=alloc("out-b",6*sizeof(uint64_t));cache_arena=alloc("tiny-cache-arena",512+255);
  for(size_t i=0;i<144;++i){a[i]=alloc("table-a",table_bytes);b[i]=alloc("table-b",table_bytes);decoy[i]=alloc("decoy",table_bytes);std::memset(ptr(decoy[i]),0xa5,table_bytes);}
  for(unsigned g=1;g<=2;++g){auto*p=static_cast<uint64_t*>(ptr(g==1?bank1:bank2));for(unsigned l=0;l<48;++l)for(unsigned projection=0;projection<3;++projection)for(unsigned e=0;e<512;++e)p[(l*3+projection)*512+e]=payload_value(g,l,projection,e);}
  for(unsigned which=0;which<2;++which){auto&dest=which?b:a;std::array<Allocation,4>ids{dest[0],dest[71],dest[143],which?out_b:out_a};Consumer op;device.begin_capture(consumers[which]);try{device.compute(op,ids,{});device.end_capture();}catch(...){device.end_capture();throw;}need(consumers[which].size()==1,"actual prepared pointerconsumer");}
 }
 ~Fixture(){if(!closed){auto r=device.shutdown(std::chrono::milliseconds(100));if(!r.safe_to_exit){std::cerr<<"retained fixture: "<<r.json()<<'\n';std::abort();}}}
 Allocation alloc(const char*name,size_t n,Memory memory=Memory::device){auto id=device.arena.allocate("p214:"+std::to_string(++count)+":"+name,n,memory,memory==Memory::pinned?Category::pinned_slab:Category::scratch,memory==Memory::pinned?Lifetime::transfer:Lifetime::transaction);std::memset(device.arena.row(id).pointer,0,n);return id;}
 void*ptr(Allocation id){return device.arena.row(id).pointer;}
 std::vector<p58::Entry> entries(unsigned generation){std::vector<p58::Entry> result(48*512);auto base=uint64_t(ptr(generation==1?bank1:bank2));for(unsigned l=0;l<48;++l)for(unsigned e=0;e<512;++e)result[l*512+e]={base+((l*3)*512+e)*8,base+((l*3+1)*512+e)*8,base+((l*3+2)*512+e)*8,generation};return result;}
 std::vector<unsigned char> expected(unsigned generation){std::vector<unsigned char> v(total_bytes);auto*p=reinterpret_cast<Pointer*>(v.data());auto base=uint64_t(ptr(generation==1?bank1:bank2));for(unsigned i=0;i<144;++i)for(unsigned e=0;e<512;++e)p[i*512+e]={base+(i*512+e)*8,generation};return v;}
 std::vector<unsigned char> bytes(const std::array<Allocation,144>&dest){std::vector<unsigned char>v;v.reserve(total_bytes);for(auto id:dest){auto*p=static_cast<unsigned char*>(ptr(id));v.insert(v.end(),p,p+table_bytes);}return v;}
 void drain(){for(auto e:events)need(device.wait(e,std::chrono::milliseconds(100))&&device.complete(e),"pending consumer");events.clear();need(device.in_flight()==0,"owner inflight");device.retire_completed_events();}
 bool consumed(unsigned which,unsigned generation){events.push_back(device.issue(consumers[which][0]));drain();auto*p=static_cast<uint64_t*>(ptr(which?out_b:out_a));std::array<unsigned,3>ids{0,71,143},slots{0,17,511};for(unsigned i=0;i<3;++i)if(p[i*2]!=payload_value(generation,ids[i]/3,ids[i]%3,slots[i])||p[i*2+1]!=generation)return false;return true;}
 bool decoys_intact(){for(auto id:decoy){auto*p=static_cast<unsigned char*>(ptr(id));for(size_t j=0;j<table_bytes;++j)if(p[j]!=0xa5)return false;}return true;}
 Receipt finish(){drain();auto r=device.shutdown(std::chrono::milliseconds(100));need(r.safe_to_exit&&r.in_flight==0&&r.live_bytes==0,"owner close");closed=true;return r;}
 std::unique_ptr<p58::Cache> full_cache(){auto rows=entries(1);std::vector<p58::Expert> e;for(auto r:rows)e.push_back({r.gate,r.up,r.down,8,8,8});auto base=(uint64_t(ptr(cache_arena))+255)&~uint64_t(255);return std::make_unique<p58::Cache>(std::move(e),base,512);}
};
std::array<p214::TableBinding,144> bindings(const std::array<Allocation,144>&ids){std::array<p214::TableBinding,144> result{};for(unsigned i=0;i<144;++i)result[i]={ids[i],i/3,i%3};return result;}
}
int main(){try{
 std::map<std::string,bool>checks;std::map<std::string,std::string>receipts,hashes,errors;auto pass=[&](std::string n,bool v){need(v,n.c_str());checks[n]=true;};
 {
  Fixture f;auto caller_a=bindings(f.a),caller_b=bindings(f.b);std::rotate(caller_a.begin(),caller_a.begin()+13,caller_a.end());std::rotate(caller_b.begin(),caller_b.begin()+37,caller_b.end());p214::Publisher copies(f.device,*f.host,f.stage_a,f.upload_a,caller_a),kernel(f.device,*f.host,f.stage_b,f.upload_b,caller_b);caller_a=bindings(f.decoy);caller_b=bindings(f.decoy);
  for(unsigned generation=1;generation<=2;++generation){auto table=f.entries(generation);auto x=copies.publish(table,p214::PublicationMode::copies),y=kernel.publish(table,p214::PublicationMode::kernel);copies.complete(std::chrono::milliseconds(100));kernel.complete(std::chrono::milliseconds(100));
   pass("full_table_exact_generation"+std::to_string(generation),f.bytes(f.a)==f.expected(generation)&&f.bytes(f.b)==f.expected(generation)&&f.bytes(f.a)==f.bytes(f.b));
   pass("transfer_shape_generation"+std::to_string(generation),x.operations==144&&y.operations==1&&x.bytes==total_bytes&&y.bytes==total_bytes);
   pass("actual_prepared_pointer_consumers_generation"+std::to_string(generation),f.consumed(0,generation)&&f.consumed(1,generation));hashes["generation"+std::to_string(generation)]=sha(f.bytes(f.a));
  }
  pass("two_generations_differ",hashes["generation1"]!=hashes["generation2"]);pass("fixed_destinations_ignore_caller_array_decoys",f.decoys_intact());
  pass("healthy_helpers_close_release",copies.close(std::chrono::milliseconds(100))&&kernel.close(std::chrono::milliseconds(100))&&copies.release_allowed()&&kernel.release_allowed()&&!copies.poisoned()&&!kernel.poisoned());receipts["healthy_two_generations"]=f.finish().json();
 }
 {
  Fixture f;auto bad=bindings(f.a);bad[1].id=bad[0].id;pass("duplicate_destination_refused",refuses([&]{p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bad);}));
  bad=bindings(f.a);bad[17].layer=0;pass("wrong_logical_destination_refused",refuses([&]{p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bad);}));
  pass("staging_publication_alias_refused",refuses([&]{p214::Publisher p(f.device,*f.host,f.stage_a,f.stage_a,bindings(f.a));}));
  pass("publication_destination_alias_refused",refuses([&]{p214::Publisher p(f.device,*f.host,f.stage_a,f.a[0],bindings(f.a));}));
  auto short_stage=f.alloc("short-stage",total_bytes-8,Memory::pinned);pass("short_actual_staging_extent_refused",refuses([&]{p214::Publisher p(f.device,*f.host,short_stage,f.upload_a,bindings(f.a));}));
  auto short_table=f.alloc("short-table",table_bytes-8);bad=bindings(f.a);bad[0].id=short_table;pass("short_actual_destination_extent_refused",refuses([&]{p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bad);}));
  for(unsigned kind=0;kind<4;++kind){p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bindings(f.a));auto before=f.bytes(f.a);auto rows=f.entries(1);if(kind==0)rows.pop_back();if(kind==1)rows[17].generation=0;if(kind==2)rows[19].gate=0;
   std::string name=std::array<std::string,4>{"short_input_table_refused","zero_generation_refused","zero_pointer_refused","readers_active_publication_refused"}[kind];pass(name,refuses([&]{p.publish(rows,p214::PublicationMode::kernel,kind==3);})&&f.bytes(f.a)==before&&!p.pending()&&!p.uncertain());need(p.close(std::chrono::milliseconds(100)),"invalid input cleanup");}
  receipts["invalid_bindings"]=f.finish().json();
 }
 {
  Fixture f;p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bindings(f.a));auto before=f.bytes(f.a);f.device.arena.release(f.a[0]);
  pass("released_storage_refuses_publication",refuses([&]{p.publish(f.entries(1),p214::PublicationMode::kernel);}));
  pass("stale_refusal_has_no_pending_submission",!p.pending()&&!p.uncertain());pass("stale_refusal_close_safe",p.close(std::chrono::milliseconds(100)));receipts["released_storage"]=f.finish().json();
 }
 {
  Fixture f;p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bindings(f.a));std::vector<PreparedCompute>captured;auto before=f.bytes(f.a);f.device.begin_capture(captured);bool rejected=refuses([&]{p.publish(f.entries(1),p214::PublicationMode::kernel);});f.device.end_capture();
  pass("capture_refused_before_publish_operation",rejected&&captured.empty()&&f.bytes(f.a)==before&&!p.pending()&&!p.uncertain());pass("capture_refusal_close_safe",p.close(std::chrono::milliseconds(100)));receipts["capture_refusal"]=f.finish().json();
 }
 {
  Fixture f;p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bindings(f.a));f.host->auto_marker=false;p.publish(f.entries(1),p214::PublicationMode::kernel);std::vector<unsigned char>stage(static_cast<unsigned char*>(f.ptr(f.stage_a)),static_cast<unsigned char*>(f.ptr(f.stage_a))+total_bytes);
  pass("tracked_pending_owner_event",f.device.in_flight()>0&&p.pending()&&!p.release_allowed());
  pass("pending_refuses_restage",refuses([&]{p.publish(f.entries(2),p214::PublicationMode::kernel);})&&std::memcmp(f.ptr(f.stage_a),stage.data(),total_bytes)==0);
  pass("tracked_event_raw_allocator_release_guard",refuses([&]{f.device.arena.release(f.stage_a);})&&refuses([&]{f.device.arena.release(f.a[0]);}));
  pass("pending_close_retains_storage",!p.close(std::chrono::milliseconds(0))&&!p.release_allowed()&&f.device.arena.row(f.stage_a).live&&f.device.arena.row(f.upload_a).live&&f.device.arena.row(f.a[0]).live);
  f.host->finish_all();f.host->auto_marker=true;pass("tracked_completion_allows_safe_cleanup",p.close(std::chrono::milliseconds(100))&&p.release_allowed());receipts["tracked_pending"]=f.finish().json();
 }
 {
  Fixture f;p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bindings(f.a));auto cache=f.full_cache();p213::CacheTransition control;
  p.publish(cache->table(),p214::PublicationMode::copies);p.complete(std::chrono::milliseconds(100));auto before=f.bytes(f.a);auto epoch=control.begin(*cache);control.finish(*cache,epoch,true);auto plan=control.prepare(*cache,{0,1});
  p214::Publisher::TestHooks hooks;hooks.before_copy=[&](size_t i){if(i==1){CopyEngine copy(f.device);copy.copy(f.a[1],0,f.stage_a,table_bytes,table_bytes+1,{});}};p.set_test_hooks(hooks);std::exception_ptr original;
  try{p.publish(plan.table,p214::PublicationMode::copies);}catch(const std::exception&e){original=std::current_exception();errors["partial_publication"]=e.what();control.poison(original);}
  auto after=f.bytes(f.a);pass("partial_publication_first_table_changed",original&&std::memcmp(before.data(),after.data(),table_bytes)!=0);
  pass("partial_publication_remaining_tables_unchanged",std::equal(before.begin()+table_bytes,before.end(),after.begin()+table_bytes));
  pass("partial_publication_poison_no_commit",p.poisoned()&&p.failure()==original&&control.poisoned()&&control.phase()==p213::CacheTransition::Phase::updating&&refuses([&]{control.commit(*cache,plan.epoch,true,true);})&&refuses([&]{p.publish(plan.table,p214::PublicationMode::kernel);}));
  pass("partial_publication_sync_cleanup_safe",p.close(std::chrono::milliseconds(100))&&p.release_allowed());f.drain();pass("partial_publication_failed_cache_close_not_success",control.close(*cache,true)&&!control.successful_close()&&control.failure()==original&&p.failure()==original);
  hashes["partial_before"]=sha(before);hashes["partial_after"]=sha(after);receipts["partial_publication"]=f.finish().json();
 }
 {
  Fixture f;p214::Publisher p(f.device,*f.host,f.stage_a,f.upload_a,bindings(f.a));auto cache=f.full_cache();p213::CacheTransition control;auto epoch=control.begin(*cache);control.finish(*cache,epoch,true);auto plan=control.prepare(*cache,{0});Event hidden=0;f.host->auto_marker=false;
  p214::Publisher::TestHooks hooks;hooks.before_kernel=[&]{hidden=f.host->marker({});throw std::runtime_error("injected hidden backend submission failure");};p.set_test_hooks(hooks);std::exception_ptr original;
  try{p.publish(plan.table,p214::PublicationMode::kernel);}catch(const std::exception&e){original=std::current_exception();errors["hidden_backend_submission"]=e.what();control.poison(original);}
  pass("hidden_marker_not_device_ledger",original&&hidden&&f.device.in_flight()==0&&!f.host->complete(hidden)&&p.uncertain());
  auto stage=std::vector<unsigned char>(static_cast<unsigned char*>(f.ptr(f.stage_a)),static_cast<unsigned char*>(f.ptr(f.stage_a))+total_bytes);
  pass("hidden_work_sync_failure_retains",!p.close(std::chrono::milliseconds(0))&&p.uncertain()&&!p.closed()&&!p.release_allowed()&&p.failure()==original);
  pass("hidden_work_all_storage_live",f.device.arena.row(f.stage_a).live&&f.device.arena.row(f.upload_a).live&&std::all_of(f.a.begin(),f.a.end(),[&](auto id){return f.device.arena.row(id).live;}));
  pass("hidden_work_restage_refused",refuses([&]{p.publish(f.entries(2),p214::PublicationMode::kernel);})&&std::memcmp(f.ptr(f.stage_a),stage.data(),total_bytes)==0);
  pass("hidden_work_blocks_cache_release",!control.close(*cache,p.release_allowed())&&control.phase()==p213::CacheTransition::Phase::updating);
  f.host->finish_all();f.host->auto_marker=true;pass("actual_backend_sync_then_release",p.close(std::chrono::milliseconds(100))&&!p.uncertain()&&p.release_allowed());
  pass("hidden_error_preserved_after_cleanup",p.poisoned()&&p.failure()==original&&control.close(*cache,true)&&!control.successful_close()&&control.failure()==original);receipts["hidden_backend_submission"]=f.finish().json();
 }
 std::cout<<"{\"schema\":\"packet214.publication-proof.v1\",\"passed\":true,\"device_executed\":false,\"native_executed\":false,\"model_executed\":false,\"geometry\":{\"tables\":144,\"entries_per_table\":512,\"entry_bytes\":16,\"publication_bytes\":"<<total_bytes<<"},\"scope\":\"real CPU bytes, CopyEngine and unchanged HOST Publish; simulated Host markers including hidden preledger work, not native DMA proof\",\"checks\":{";bool first=true;for(auto&[n,v]:checks){std::cout<<(first?"":",")<<quote(n)<<":true";first=false;}std::cout<<"},\"first_errors\":{";first=true;for(auto&[n,v]:errors){std::cout<<(first?"":",")<<quote(n)<<':'<<quote(v);first=false;}std::cout<<"},\"byte_sha256\":{";first=true;for(auto&[n,v]:hashes){std::cout<<(first?"":",")<<quote(n)<<':'<<quote(v);first=false;}std::cout<<"},\"owner_receipts\":{";first=true;for(auto&[n,v]:receipts){std::cout<<(first?"":",")<<quote(n)<<':'<<v;first=false;}std::cout<<"}}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
