#pragma once
#include <array>
#include <chrono>
#include <exception>
#include <functional>
#include <set>
#include <vector>
// Included after the exact pinned owner, Cache/Pointer and p58v::Publish types.
// Backend is borrowed from the same unique_ptr that constructed this Device.
// Only synchronize is called through it; all submissions go through Device.
namespace p214 {
enum class PublicationMode {copies,kernel};
struct TableBinding {ownrt::Allocation id;unsigned layer,projection;};
struct Submission {ownrt::Event last=0;size_t operations=0,bytes=0;};
class Publisher {
 ownrt::Device& d;ownrt::Backend& backend;
 ownrt::Allocation staging,publication;std::array<TableBinding,144> tables;
 std::array<ownrt::Event,144> events{};size_t event_count=0;
 std::array<ownrt::Allocation,145> kernel_ids{};uint64_t generation;
 bool poisoned_=false,uncertain_=false,closed_=false;std::exception_ptr failure_;
 static constexpr size_t entries=512,table_bytes=entries*sizeof(p58::Pointer),all_bytes=144*table_bytes;
 static void require(bool ok,const char* text){if(!ok)throw std::invalid_argument(text);}
 void poison()noexcept{poisoned_=true;if(!failure_)failure_=std::current_exception();}
 void validate()const{
  require(d.generation()==generation,"p214 owner generation changed");
  const auto&s=d.arena.row(staging);const auto&p=d.arena.row(publication);
  require(s.live&&s.memory==ownrt::Memory::pinned&&s.bytes==all_bytes,"p214 exact pinned staging extent");
  require(p.live&&p.memory==ownrt::Memory::device&&p.bytes==all_bytes,"p214 exact publication extent");
  std::set<ownrt::Allocation> ids{staging,publication};require(ids.size()==2,"p214 staging/publication alias");std::array<bool,144> seen{};
  for(const auto&b:tables){require(b.layer<48&&b.projection<3&&!seen[b.layer*3+b.projection],"p214 exact unique layer/projection");seen[b.layer*3+b.projection]=true;require(ids.insert(b.id).second,"p214 table writable alias");const auto&r=d.arena.row(b.id);require(r.live&&r.memory==ownrt::Memory::device&&r.bytes==table_bytes,"p214 exact table extent");}
 }
 void wait_known(std::chrono::milliseconds timeout){const auto end=std::chrono::steady_clock::now()+timeout;for(size_t i=0;i<event_count;++i){auto remaining=std::chrono::duration_cast<std::chrono::milliseconds>(end-std::chrono::steady_clock::now());require(remaining.count()>0&&d.wait(events[i],remaining)&&d.complete(events[i]),"p214 publication incomplete");}}
#ifdef OWN_RT_HOST_ONLY
public:
 struct TestHooks {std::function<void(size_t)> before_copy;std::function<void()> before_kernel;};
private:
 TestHooks hooks;
#endif
public:
 Publisher(ownrt::Device&device,ownrt::Backend&owned_backend,ownrt::Allocation stage,ownrt::Allocation transfer,std::array<TableBinding,144> bindings):d(device),backend(owned_backend),staging(stage),publication(transfer),tables(std::move(bindings)),generation(d.generation()){
  static_assert(sizeof(p58::Pointer)==16);validate();kernel_ids[0]=publication;for(size_t i=0;i<144;++i)kernel_ids[i+1]=tables[i].id;
 }
 // Explicit completion is mandatory. The destructor never touches borrowed
 // Device/Backend references, which may already have been shut down.
 ~Publisher()=default;
 bool poisoned()const noexcept{return poisoned_;}bool uncertain()const noexcept{return uncertain_;}
 bool pending()const noexcept{return event_count!=0;}bool closed()const noexcept{return closed_;}
 bool ready()const noexcept{return !poisoned_&&!uncertain_&&!pending()&&!closed_;}
 bool release_allowed()const noexcept{return closed_&&!uncertain_&&!pending();}
 std::exception_ptr failure()const noexcept{return failure_;}
#ifdef OWN_RT_HOST_ONLY
 void set_test_hooks(TestHooks value){require(!pending()&&!uncertain_&&!closed_,"p214 test hooks while owned");hooks=std::move(value);}
#endif
 Submission publish(const std::vector<p58::Entry>& table,PublicationMode mode,bool readers_active=false){try{
  require(!poisoned_&&!closed_&&!uncertain_&&!pending(),"p214 halted/busy publication");require(!readers_active,"p214 publication during readers");
  require(!d.capturing(),"p214 immediate publisher refuses capture");require(d.in_flight()==0,"p214 prior owner work incomplete");
  require(mode==PublicationMode::copies||mode==PublicationMode::kernel,"p214 publisher mode");validate();require(table.size()==48*entries,"p214 complete Cache table extent");
  for(const auto&e:table)require(e.gate&&e.up&&e.down&&e.generation,"p214 empty pointer/generation");
  auto* out=static_cast<p58::Pointer*>(d.arena.row(staging).pointer);std::array<uint64_t*,144> destinations{};
  for(size_t i=0;i<144;++i){const auto&b=tables[i];destinations[i]=static_cast<uint64_t*>(d.arena.row(b.id).pointer);for(size_t j=0;j<entries;++j){const auto&e=table[b.layer*entries+j];out[i*entries+j]={b.projection==0?e.gate:b.projection==1?e.up:e.down,e.generation};}}
  Submission result;result.bytes=all_bytes;
  if(mode==PublicationMode::kernel){uncertain_=true;
#ifdef OWN_RT_HOST_ONLY
   if(hooks.before_kernel)hooks.before_kernel();
#endif
   p58v::Publish op(destinations,entries*2,out);
   // Type erasure deliberately bypasses template audit_prepare_each/capture.
   // The unchanged native operation must never enter backend prepare().
   auto event=d.compute(static_cast<const ownrt::Operation&>(op),kernel_ids,{});events[event_count++]=event;uncertain_=false;result.last=event;result.operations=1;
  }else{ownrt::CopyEngine copy(d);for(size_t i=0;i<144;++i){uncertain_=true;
#ifdef OWN_RT_HOST_ONLY
   if(hooks.before_copy)hooks.before_copy(i);
#endif
   auto event=copy.copy(tables[i].id,0,staging,i*table_bytes,table_bytes,{});events[event_count++]=event;uncertain_=false;result.last=event;++result.operations;}}
  return result;
 }catch(...){poison();throw;}}
 void complete(std::chrono::milliseconds timeout){try{require(!uncertain_,"p214 uncertain submission requires full synchronization");wait_known(timeout);require(d.in_flight()==0,"p214 remaining owner work");event_count=0;}catch(...){uncertain_=true;poison();throw;}}
 // An empty Device ledger is never an uncertainty proof. This always invokes
 // the exact owned Backend's full synchronization before granting cleanup.
 bool close(std::chrono::milliseconds timeout)noexcept{if(closed_)return true;try{wait_known(timeout);backend.synchronize();require(d.in_flight()==0,"p214 full sync left owned work");event_count=0;uncertain_=false;closed_=true;return true;}catch(...){uncertain_=true;poison();return false;}}
};
} // namespace p214
