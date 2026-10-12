#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <sycl/ext/oneapi/experimental/graph.hpp>
#include <optional>
namespace replay34 {
namespace gx=sycl::ext::oneapi::experimental;
// Borrowing graph objects are always explicitly cleared before owner buffers.
// No raw list/ABI guessing. This backend implements the packet29 resident
// same-card dependency policy: validate owner handles, pass empty SYCL deps.
class Native final:public ownrt::Backend {
 struct Entry {std::optional<sycl::event> event;bool capture=false;bool kernel=false;};
 std::map<ownrt::Event,Entry> events;
 ze_context_handle_t native=nullptr;
 std::unique_ptr<sycl::context> context;
 std::unique_ptr<sycl::queue> queue;
 std::exception_ptr error;
 std::mutex mutex;
 bool uncertain=false;
 bool capturing=false;
 std::optional<uint64_t> recording_free_baseline;
 bool replay_pending=false;
 std::optional<sycl::event> replay_tail;
 std::map<void*,std::pair<size_t,ownrt::Memory>> allocations;
 struct Graph {
  std::unique_ptr<gx::command_graph<gx::graph_state::modifiable>> source;
  std::unique_ptr<gx::command_graph<gx::graph_state::executable>> exec;
  size_t nodes=0,required_bytes=0;
 };
 std::vector<std::unique_ptr<Graph>> graphs;
 std::string label;
 void check(){std::lock_guard lock(mutex);if(error)std::rethrow_exception(error);if(uncertain)throw std::runtime_error("uncertain native submission; retain owner");}
 void deps(std::span<const ownrt::Event> d){for(auto e:d)if(!events.contains(e))throw std::logic_error("foreign queue dependency");}
 template<class F> ownrt::Event issue(F f,bool kernel){
  check();auto id=ownrt::next_handle();auto& entry=events[id];entry.capture=capturing;entry.kernel=kernel;
  uncertain=true;entry.event=f();uncertain=false;return id;
 }
public:
 size_t issued=0;
 explicit Native(int card){
  std::vector<sycl::device> devices;
  for(auto p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)
   for(auto d:p.get_devices(sycl::info::device_type::gpu))devices.push_back(d);
  if(card<0||size_t(card)>=devices.size())throw std::invalid_argument("card index");
  auto d=devices[card];label="packet34:LevelZero:"+std::to_string(card)+":"+d.get_info<sycl::info::device::name>();
  auto handler=[this](sycl::exception_list errors){std::lock_guard lock(mutex);if(!error&&errors.size())error=*errors.begin();};
  ze_context_desc_t desc{};desc.stype=ZE_STRUCTURE_TYPE_CONTEXT_DESC;
  auto driver=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d.get_platform());
  if(zeContextCreate(driver,&desc,&native)!=ZE_RESULT_SUCCESS)throw std::runtime_error("native context create");
  try{
   context=std::make_unique<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>({native,{d},sycl::ext::oneapi::level_zero::ownership::keep},handler));
   queue=std::make_unique<sycl::queue>(*context,d,handler,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  }catch(...){queue.reset();context.reset();if(zeContextDestroy(native)!=ZE_RESULT_SUCCESS)ownrt::hold_for_supervisor();native=nullptr;throw;}
 }
 ~Native()override{if(native||context||queue||!graphs.empty())ownrt::hold_for_supervisor();}
 std::string identity()const override{return label;}
 void* allocate(size_t n,ownrt::Memory m)override{
  check();if(capturing||!graphs.empty())throw std::logic_error("allocate after capture");
  void* ptr=m==Memory::device?sycl::malloc_device(n,*queue):m==Memory::pinned?sycl::malloc_host(n,*context) : ::operator new(n);
  if(ptr)try{allocations.emplace(ptr,std::make_pair(n,m));}
  catch(...){
   // A failed host bookkeeping allocation must not orphan native storage.
   try{if(m==Memory::shadow)::operator delete(ptr);else sycl::free(ptr,*context);}
   catch(...){ownrt::hold_for_supervisor();}
   throw;
  }
  return ptr;
 }
 void release(void* p,ownrt::Memory m)override{
  if(capturing||replay_pending||!graphs.empty())throw std::logic_error("release with recorder lease");
  if(allocations.at(p).second!=m)throw std::logic_error("release memory identity");
  if(m==Memory::shadow)::operator delete(p);else sycl::free(p,*context);allocations.erase(p);
 }
 ownrt::Event compute(const ownrt::Operation& op,std::span<void*const> p,std::span<const ownrt::Event> d)override{
  deps(d);++issued;const auto& o=dynamic_cast<const ownrt::SyclOperation&>(op);
  return issue([&]{return o.submit(*queue,p,{});},true);
 }
 ownrt::Event copy(void* a,const void* b,size_t n,std::span<const ownrt::Event> d)override{
  if(capturing||replay_pending)throw std::logic_error("copy during capture/replay");deps(d);
  return issue([&]{return queue->memcpy(a,b,n);},false);
 }
 ownrt::Event marker(std::span<const ownrt::Event> d)override{
  deps(d);return issue([&]{return queue->single_task(packet26::checked([]{}));},false);
 }
 bool complete(ownrt::Event e)override{
  check();auto& v=events.at(e);if(v.capture)return true;
  return v.event&&v.event->get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;
 }
 bool wait(ownrt::Event e,ownrt::Deadline end)override{
  while(!complete(e)){if(std::chrono::steady_clock::now()>=end)return false;std::this_thread::yield();}
  auto& v=events.at(e);if(!v.capture)v.event->wait_and_throw();check();return true;
 }
 ownrt::EventTiming timing(ownrt::Event e)override{
  check();auto& v=events.at(e);if(v.capture||!v.event)throw std::logic_error("capture event has no timing");
  return {v.event->get_profiling_info<sycl::info::event_profiling::command_start>(),v.event->get_profiling_info<sycl::info::event_profiling::command_end>()};
 }
 void synchronize()override{if(capturing)throw std::logic_error("wait during capture");check();queue->wait_and_throw();check();}
 void clear_events()override{if(capturing)throw std::logic_error("retire during capture");events.clear();}
 void close_queue()override{if(!graphs.empty()||replay_pending||!events.empty()||!allocations.empty())throw std::logic_error("queue borrower survives");queue.reset();}
 void close_context()override{if(queue)throw std::logic_error("context before queue");context.reset();if(zeContextDestroy(native)!=ZE_RESULT_SUCCESS)throw std::runtime_error("context release");native=nullptr;}
 std::optional<uint64_t> free_bytes(){
  check();auto d=queue->get_device();if(!d.has(sycl::aspect::ext_intel_free_memory))return {};
  try{return d.get_info<sycl::ext::intel::info::device::free_memory>();}
  catch(const sycl::exception& ex){if(ex.code()!=sycl::errc::feature_not_supported&&ex.code()!=sycl::errc::invalid)throw;return {};}
 }
 size_t begin(){
  check();auto free=free_bytes();if(free){
   if(!recording_free_baseline)recording_free_baseline=free;
   if(*free<2ull*1024*1024*1024)throw std::runtime_error("less than2GiB free before next recording");
  }if(capturing||replay_pending||!queue->ext_oneapi_empty())throw std::logic_error("capture needs idle owner");
  auto g=std::make_unique<Graph>();g->source=std::make_unique<gx::command_graph<gx::graph_state::modifiable>>(*context,queue->get_device());
  graphs.push_back(std::move(g));
  // If begin throws, cleanup still sees and ends this possible capture.
  capturing=true;graphs.back()->source->begin_recording(*queue);return graphs.size()-1;
 }
 void end(){
  if(!capturing)throw std::logic_error("no capture");auto& g=*graphs.back();
  g.source->end_recording(*queue);capturing=false;
  for(auto n:g.source->get_nodes()){
   if(n.get_type()==gx::node_type::kernel)++g.nodes;
   else if(n.get_type()!=gx::node_type::empty&&n.get_type()!=gx::node_type::ext_oneapi_barrier)throw std::runtime_error("unsupported graph node");
  }
  if(!g.nodes)throw std::runtime_error("empty graph");
  // Only direct events are profiled: graph internal profiling is not needed.
  g.exec=std::make_unique<gx::command_graph<gx::graph_state::executable>>(g.source->finalize());
  g.required_bytes=g.exec->get_required_mem_size();
  if(graph_bytes()>1024ull*1024*1024)throw std::runtime_error("graph memory budget exceeded (1 GiB)");
  auto free=free_bytes();if(free&&recording_free_baseline&&*recording_free_baseline>*free&&*recording_free_baseline-*free>1024ull*1024*1024)
   throw std::runtime_error("driver-reported recording growth exceeds1GiB; stop before next graph");
 }
 std::string driver_memory(){
  check();
  // Optional installed SYCL counter, queried only on this owner's device.
  auto d=queue->get_device();
  if(!d.has(sycl::aspect::ext_intel_free_memory))return "{\"available\":false,\"reason\":\"owner device lacks ext_intel_free_memory; allocation accounting only\"}";
  try{auto free=d.get_info<sycl::ext::intel::info::device::free_memory>();auto total=d.get_info<sycl::info::device::global_mem_size>();
   return "{\"available\":true,\"free_bytes\":"+std::to_string(free)+",\"total_bytes\":"+std::to_string(total)+"}";
  }catch(const sycl::exception& ex){if(ex.code()!=sycl::errc::feature_not_supported&&ex.code()!=sycl::errc::invalid)throw;
   return "{\"available\":false,\"reason\":"+ownrt::quote(ex.what())+"}";}
 }
 size_t graph_bytes()const{size_t n=0;for(const auto& g:graphs)n+=g->required_bytes;return n;}
 size_t graph_count()const{return graphs.size();}
 size_t nodes(size_t i)const{return graphs.at(i)->nodes;}
 void replay(size_t i){
  check();if(capturing||i>=graphs.size()||!graphs[i]->exec)throw std::logic_error("unfinalized replay");
  replay_tail.reset();replay_pending=true;uncertain=true;
  replay_tail=queue->submit([&](sycl::handler& h){h.ext_oneapi_graph(*graphs[i]->exec);});uncertain=false;
 }
 bool drain_replay(ownrt::Deadline end){
  check();if(!replay_pending)return true;if(!replay_tail)return false;
  while(replay_tail->get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){check();if(std::chrono::steady_clock::now()>=end)return false;std::this_thread::yield();}
  replay_tail->wait_and_throw();check();replay_pending=false;return true;
 }
 void clear_recordings(){
  check();if(replay_pending)throw std::logic_error("clear busy graph");
  if(capturing){graphs.back()->source->end_recording(*queue);capturing=false;}
  // Captured events are topology, but all eager work must have completed before
  // dropping its last event wrapper or graph allocation leases.
  for(const auto& [id,event]:events)if(!event.capture&&!complete(id))throw std::logic_error("clear with eager work pending");
  if(!queue->ext_oneapi_empty())throw std::logic_error("clear before owner queue idle");
  replay_tail.reset();
  // The owner may still hold integer capture IDs on an exception path. Drop
  // graph event wrappers now, but keep completed synthetic ledger rows until
  // owner shutdown/retirement clears them; erasing IDs here breaks its drain.
  for(auto& [id,event]:events)if(event.capture)event.event.reset();
  for(auto it=graphs.rbegin();it!=graphs.rend();++it){(*it)->exec.reset();(*it)->source.reset();}
  graphs.clear();
 }
};
} // namespace replay34
#endif
