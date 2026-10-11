// Packet20: CPU compilation is permitted; NEVER execute during FAULT HALT.
#include "owner.hpp"
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <sycl/ext/oneapi/experimental/graph.hpp>
#include <level_zero/ze_api.h>
#include <array>
#include <bit>
#include <atomic>
#include <csignal>
#include <cstring>
#include <mutex>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <variant>
using Clock=std::chrono::steady_clock;
namespace gx=sycl::ext::oneapi::experimental;
static volatile std::sig_atomic_t stopped=0;
static void signal_stop(int){stopped=1;}
static void ze(ze_result_t x){if(x!=ZE_RESULT_SUCCESS)throw std::runtime_error("Level Zero status="+std::to_string(x));}
struct Trial:ownrt::Operation {std::string method;int n,kind;std::ostream* rows;bool* available;};
struct Unsupported:std::runtime_error{using std::runtime_error::runtime_error;};
struct Pointers {std::array<uint16_t*,17> p;};
// All 17 pointer fields used; device-state p16 carries mutable replay inputs.
struct Work {
 Pointers a;int operations,kind;
 void operator()(sycl::id<1> id)const{
  size_t j=id[0];auto state=reinterpret_cast<uint32_t*>(a.p[16])[0];
  float sign=(state&1)?-1.f:1.f;
  float x=sycl::bit_cast<float>(uint32_t(a.p[0][j])<<16);
  for(int op=0;op<operations;++op){
   if(kind==0){for(int k=1;k<16;k++)x=x+sign*sycl::bit_cast<float>(uint32_t(a.p[k][j])<<16);}
   else {for(int k=0;k<32;k++)x=x+sign*sycl::bit_cast<float>(uint32_t(a.p[1][(j+k)%2560])<<16)*sycl::bit_cast<float>(uint32_t(a.p[2][k])<<16);}
   auto bits=sycl::bit_cast<uint32_t>(x);
   auto b=uint16_t((bits+0x7fff+((bits>>16)&1))>>16);x=sycl::bit_cast<float>(uint32_t(b)<<16);
  }
  a.p[0][j]=uint16_t(sycl::bit_cast<uint32_t>(x)>>16);
 }
};
class Backend final:public ownrt::Backend {
 std::unique_ptr<sycl::context> c;
 std::unique_ptr<sycl::queue> q;
 sycl::device d;
 ze_context_handle_t context=nullptr;ze_device_handle_t device=nullptr;
 ze_device_properties_t properties{};
 struct End{Clock::time_point wall;std::pair<uint64_t,uint64_t> device;};
 End finish(){auto wall=Clock::now();return{wall,stamp()};}
 std::map<ownrt::Event,sycl::event> events;
 std::exception_ptr error;std::mutex errors;Clock::time_point deadline;
 void save_error(sycl::exception_list e){std::lock_guard lock(errors);if(!error&&e.size())error=*e.begin();}
 void check_error(){std::lock_guard lock(errors);if(error)std::rethrow_exception(error);}
 std::filesystem::path spirv;
 bool active=false;
 std::array<uint32_t,2> token_state{};
 std::array<uint16_t,2560> staging{},output{};
 void admission(){if(stopped||Clock::now()>deadline)throw std::runtime_error("cooperative deadline/stop");check_error();}
 void poll(sycl::event e){auto end=std::min(deadline,Clock::now()+std::chrono::milliseconds(900));while(e.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){if(Clock::now()>end)throw std::runtime_error("submission exceeded 900ms bound");std::this_thread::sleep_for(std::chrono::microseconds(100));}e.wait_and_throw();check_error();}
 void empty(sycl::queue& queue){auto end=std::min(deadline,Clock::now()+std::chrono::milliseconds(900));while(!queue.ext_oneapi_empty()){if(Clock::now()>end)throw std::runtime_error("queue exceeded 900ms bound");std::this_thread::sleep_for(std::chrono::microseconds(100));}queue.wait_and_throw();}
 template<class F>void raw_wait(F test){auto end=std::min(deadline,Clock::now()+std::chrono::milliseconds(900));for(;;){auto v=test();if(v==ZE_RESULT_SUCCESS)break;if(v!=ZE_RESULT_NOT_READY)ze(v);if(Clock::now()>end)throw std::runtime_error("raw completion exceeded 900ms bound");std::this_thread::sleep_for(std::chrono::microseconds(100));}}
 std::pair<uint64_t,uint64_t> stamp(){uint64_t host,dev;ze(zeDeviceGetGlobalTimestamps(device,&host,&dev));return{host,dev};}
 void row(const Trial&t,int repeat,int launches,Clock::time_point begin,std::pair<uint64_t,uint64_t> first,double span,double setup_ms,End end){
  auto completed=end.wall;auto last=end.device;const auto& prop=properties;
  uint64_t mask=prop.timestampValidBits>=64?~uint64_t(0):(uint64_t(1)<<prop.timestampValidBits)-1;
  double device_ns=double((last.second-first.second)&mask)*prop.timerResolution;
  double wall_ns=std::chrono::duration<double,std::nano>(completed-begin).count();
  *t.rows<<"{\"method\":"<<ownrt::quote(t.method)<<",\"workload\":"<<ownrt::quote(t.kind?"gemv_like":"bf16_elementwise_17ptr")<<",\"n\":"<<t.n<<",\"launches\":"<<launches<<",\"repeat\":"<<repeat<<",\"wall_ns\":"<<wall_ns<<",\"wall_ns_per_launch\":"<<wall_ns/launches<<",\"device_envelope_ns\":"<<device_ns<<",\"device_envelope_ns_per_launch\":"<<device_ns/launches<<",\"profiled_span_ns\":";
  if(span<0)*t.rows<<"null";else *t.rows<<span;
  *t.rows<<",\"output_verified\":true,\"setup_ms\":"<<setup_ms<<",\"state_copy_timed\":false,\"device_envelope_definition\":\"global timestamps before issuing and after completion; includes host issue gaps\"}\n";t.rows->flush();
 }
 sycl::event submit(sycl::queue& queue,Pointers a,int ops,int kind,const std::vector<sycl::event>&deps){return queue.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::range<1>(2560),Work{a,ops,kind});});}
 void state(Pointers a,int repeat,int kind){token_state={uint32_t(repeat),uint32_t(kind)};staging.fill(0x3a80);poll(q->memcpy(a.p[0],staging.data(),5120));poll(q->memcpy(a.p[16],token_state.data(),sizeof(token_state)));}
 void validate(const Trial&t,Pointers a,int repeat){
  poll(q->memcpy(output.data(),a.p[0],5120));float value=std::bit_cast<float>(uint32_t(0x3a80)<<16),input=value;float sign=repeat&1?-1.f:1.f;
  for(int step=0;step<t.n;step++){if(t.kind==0){for(int k=1;k<16;k++)value=value+sign*input;}else{for(int k=0;k<32;k++)value=value+sign*input*input;}uint32_t b=std::bit_cast<uint32_t>(value);value=std::bit_cast<float>(uint32_t(uint16_t((b+0x7fff+((b>>16)&1))>>16))<<16);}
  auto expected=uint16_t(std::bit_cast<uint32_t>(value)>>16);for(auto b:output)if(b!=expected)throw std::runtime_error("microbenchmark output/state exactness failed");
 }
 void run_sycl(const Trial&t,Pointers a){
  if(t.method=="graph"&&!d.has(sycl::aspect::ext_oneapi_graph)&&!d.has(sycl::aspect::ext_oneapi_limited_graph))throw Unsupported("Level Zero device advertises no command graph aspect");
  bool discard=t.method=="discard_in_order",out=t.method=="explicit_out_of_order",implicit=t.method=="implicit_in_order"||discard;
  auto handler=[this](sycl::exception_list e){save_error(e);};
  sycl::property_list props=discard?sycl::property_list{sycl::property::queue::in_order{},sycl::ext::oneapi::property::queue::discard_events{}}:out?sycl::property_list{sycl::property::queue::enable_profiling{}}:sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}};
  auto queue=new sycl::queue(*c,d,handler,props);
  gx::command_graph<gx::graph_state::executable>* executable=nullptr;
  auto setup=Clock::now();int launches=t.method=="fusion8"?(t.n+7)/8:t.n;
  // No H2D/D2H or host tasks during recording. Fixed pointers only.
  if(t.method=="graph"){
   gx::command_graph graph{*c,d};graph.begin_recording(*queue);
   for(int i=0;i<t.n;i++){admission();submit(*queue,a,1,t.kind,{});}graph.end_recording(*queue);
   executable=new gx::command_graph<gx::graph_state::executable>(graph.finalize());
  }
  double setup_ms=std::chrono::duration<double,std::milli>(Clock::now()-setup).count();
  for(int repeat=0;repeat<5;repeat++){
   admission();state(a,repeat,t.kind);std::vector<sycl::event> retained;retained.reserve(launches);std::map<ownrt::Event,sycl::event> owner_events;
   auto first=stamp();auto begin=Clock::now();double span=-1;End ended;
   if(executable){auto e=queue->ext_oneapi_graph(*executable);poll(e);ended=finish();span=double(e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>());}
   else {
    for(int i=0;i<launches;i++){
     admission();std::vector<sycl::event> deps;if(!implicit&&!retained.empty())deps.push_back(retained.back());
     auto e=submit(*queue,a,t.method=="fusion8"?std::min(8,t.n-i*8):1,t.kind,deps);
     if(t.method=="explicit_wait_each")poll(e);
     if(!implicit){retained.push_back(e);if(t.method.starts_with("explicit_"))owner_events.emplace(ownrt::next_handle(),e);}
    }
    if(implicit){empty(*queue);ended=finish();}else{poll(retained.back());ended=finish();span=double(retained.back().get_profiling_info<sycl::info::event_profiling::command_end>()-retained.front().get_profiling_info<sycl::info::event_profiling::command_start>());}
   }
   validate(t,a,repeat);row(t,repeat,launches,begin,first,span,setup_ms,ended);
  }
  delete executable;delete queue;
  // Both graph and queue destroyed while allocation bindings are still live.
 }
 void run_raw(const Trial&t,Pointers a){
  auto setup=Clock::now();std::ifstream f(spirv,std::ios::binary);std::vector<char> bytes((std::istreambuf_iterator<char>(f)),{});if(bytes.empty())throw std::runtime_error("missing raw.spv");
  ze_module_desc_t md{};md.stype=ZE_STRUCTURE_TYPE_MODULE_DESC;md.format=ZE_MODULE_FORMAT_IL_SPIRV;md.inputSize=bytes.size();md.pInputModule=reinterpret_cast<const uint8_t*>(bytes.data());md.pBuildFlags="";
  ze_module_handle_t module=nullptr;ze(zeModuleCreate(context,device,&md,&module,nullptr));
  ze_kernel_desc_t kd{};kd.stype=ZE_STRUCTURE_TYPE_KERNEL_DESC;kd.pKernelName="bench";ze_kernel_handle_t kernel=nullptr;ze(zeKernelCreate(module,&kd,&kernel));
  for(uint32_t i=0;i<17;i++)ze(zeKernelSetArgumentValue(kernel,i,sizeof(void*),&a.p[i]));ze(zeKernelSetGroupSize(kernel,128,1,1));
  uint32_t count=0;ze(zeDeviceGetCommandQueueGroupProperties(device,&count,nullptr));std::vector<ze_command_queue_group_properties_t> groups(count);for(auto&g:groups)g.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;ze(zeDeviceGetCommandQueueGroupProperties(device,&count,groups.data()));uint32_t ordinal=0;while(ordinal<count&&!(groups[ordinal].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE))ordinal++;if(ordinal==count)throw std::runtime_error("no compute queue group");
  ze_command_queue_desc_t qd{};qd.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;qd.ordinal=ordinal;qd.mode=ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS;qd.priority=ZE_COMMAND_QUEUE_PRIORITY_NORMAL;
  ze_command_queue_handle_t queue=nullptr;ze_command_list_handle_t list=nullptr;bool immediate=t.method=="raw_immediate";
  if(immediate){qd.flags=ZE_COMMAND_QUEUE_FLAG_IN_ORDER;ze(zeCommandListCreateImmediate(context,device,&qd,&list));}
  else{ze(zeCommandQueueCreate(context,device,&qd,&queue));ze_command_list_desc_t ld{};ld.stype=ZE_STRUCTURE_TYPE_COMMAND_LIST_DESC;ld.commandQueueGroupOrdinal=ordinal;ld.flags=ZE_COMMAND_LIST_FLAG_IN_ORDER;ze(zeCommandListCreate(context,device,&ld,&list));}
  ze_event_pool_desc_t pd{};pd.stype=ZE_STRUCTURE_TYPE_EVENT_POOL_DESC;pd.flags=ZE_EVENT_POOL_FLAG_HOST_VISIBLE|ZE_EVENT_POOL_FLAG_KERNEL_TIMESTAMP;pd.count=3;ze_event_pool_handle_t pool=nullptr;ze(zeEventPoolCreate(context,&pd,1,&device,&pool));ze_event_desc_t ed{};ed.stype=ZE_STRUCTURE_TYPE_EVENT_DESC;ed.signal=ZE_EVENT_SCOPE_FLAG_HOST;ed.wait=ZE_EVENT_SCOPE_FLAG_DEVICE;ze_event_handle_t done=nullptr;ze(zeEventCreate(pool,&ed,&done));ze_event_handle_t first_event=nullptr,last_event=nullptr;ed.index=1;ze(zeEventCreate(pool,&ed,&first_event));ed.index=2;ze(zeEventCreate(pool,&ed,&last_event));
  ze_group_count_t gc{20,1,1};
  if(!immediate){for(int i=0;i<t.n;i++){admission();ze(zeCommandListAppendLaunchKernel(list,kernel,&gc,i==0?first_event:i==t.n-1?last_event:nullptr,0,nullptr));}ze(zeCommandListAppendBarrier(list,done,0,nullptr));ze(zeCommandListClose(list));}
  double setup_ms=std::chrono::duration<double,std::milli>(Clock::now()-setup).count();
  for(int repeat=0;repeat<5;repeat++){
   admission();state(a,repeat,t.kind);ze(zeEventHostReset(done));ze(zeEventHostReset(first_event));ze(zeEventHostReset(last_event));auto first=stamp();auto begin=Clock::now();
   if(immediate){for(int i=0;i<t.n;i++){admission();ze(zeCommandListAppendLaunchKernel(list,kernel,&gc,i==0?first_event:i==t.n-1?last_event:nullptr,0,nullptr));}ze(zeCommandListAppendBarrier(list,done,0,nullptr));}
   else ze(zeCommandQueueExecuteCommandLists(queue,1,&list,nullptr));
   raw_wait([&]{return zeEventQueryStatus(done);});
   // Signal completion precedes list completion; explicit finite sync before replay/destroy.
   if(immediate)raw_wait([&]{return zeCommandListHostSynchronize(list,0);});else raw_wait([&]{return zeCommandQueueSynchronize(queue,0);});
   auto ended=finish();
   ze_kernel_timestamp_result_t first_time{},last_time{};ze(zeEventQueryKernelTimestamp(first_event,&first_time));ze(zeEventQueryKernelTimestamp(last_event,&last_time));
   const auto& prop=properties;uint64_t mask=prop.kernelTimestampValidBits>=64?~uint64_t(0):(uint64_t(1)<<prop.kernelTimestampValidBits)-1;
   double span=double((last_time.global.kernelEnd-first_time.global.kernelStart)&mask)*prop.timerResolution;
   validate(t,a,repeat);row(t,repeat,t.n,begin,first,span,setup_ms,ended);
  }
  ze(zeCommandListDestroy(list));ze(zeEventDestroy(done));ze(zeEventDestroy(first_event));ze(zeEventDestroy(last_event));ze(zeEventPoolDestroy(pool));ze(zeKernelDestroy(kernel));ze(zeModuleDestroy(module));if(queue)ze(zeCommandQueueDestroy(queue));
 }
 public:
 Backend(size_t card,Clock::time_point end,std::filesystem::path spv):deadline(end),spirv(std::move(spv)){
  admission();std::vector<sycl::device> cards;for(auto&p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto&v:p.get_devices(sycl::info::device_type::gpu))cards.push_back(v);if(card>=cards.size())throw std::runtime_error("card index out of range");d=cards[card];
  auto handler=[this](sycl::exception_list e){save_error(e);};c=std::make_unique<sycl::context>(d,handler);q=std::make_unique<sycl::queue>(*c,d,handler,sycl::property::queue::in_order{});
  context=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(*c);device=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d);
  properties.stype=ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;ze(zeDeviceGetProperties(device,&properties));
 }
 ~Backend(){if(q||c||active)ownrt::hold_for_supervisor();}
 std::string identity()const override{return "packet20-stage1-owner-backend";}
 void*allocate(size_t n,ownrt::Memory m)override{if(m==ownrt::Memory::shadow)return ::operator new(n);return m==ownrt::Memory::device?sycl::malloc_device(n,*q):sycl::malloc_host(n,*q);}
 void release(void*p,ownrt::Memory m)override{if(m==ownrt::Memory::shadow)::operator delete(p);else sycl::free(p,*c);}
 ownrt::Event copy(void*dst,const void*src,size_t n,std::span<const ownrt::Event>deps)override{std::vector<sycl::event>w;for(auto e:deps)w.push_back(events.at(e));auto id=ownrt::next_handle();events[id]=q->submit([&](sycl::handler&h){h.depends_on(w);h.memcpy(dst,src,n);});return id;}
 ownrt::Event marker(std::span<const ownrt::Event>deps)override{std::vector<sycl::event>w;for(auto e:deps)w.push_back(events.at(e));auto id=ownrt::next_handle();events[id]=q->submit([&](sycl::handler&h){h.depends_on(w);h.single_task([]{});});return id;}
 ownrt::Event compute(const ownrt::Operation& op,std::span<void*const> p,std::span<const ownrt::Event>deps)override{
  for(auto e:deps)poll(events.at(e));const auto&t=dynamic_cast<const Trial&>(op);Pointers a;for(int i=0;i<17;i++)a.p[i]=static_cast<uint16_t*>(p[i]);admission();
  // No native resources unwind while work might be pending: retain complete
  // backend/arena and process on *any* exception after entering native method.
  active=true;try{if(t.method.starts_with("raw_"))run_raw(t,a);else run_sycl(t,a);active=false;}catch(const Unsupported&e){active=false;*t.available=false;for(int r=0;r<5;r++)*t.rows<<"{\"status\":\"unsupported\",\"method\":"<<ownrt::quote(t.method)<<",\"workload\":"<<ownrt::quote(t.kind?"gemv_like":"bf16_elementwise_17ptr")<<",\"n\":"<<t.n<<",\"repeat\":"<<r<<",\"reason\":"<<ownrt::quote(e.what())<<"}\n";}catch(const std::exception&e){std::cerr<<"HOLD: "<<e.what()<<std::endl;ownrt::hold_for_supervisor();}
  return marker({});
 }
 bool complete(ownrt::Event e)override{return events.at(e).get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;}
 bool wait(ownrt::Event e,ownrt::Deadline end)override{while(!complete(e)){if(Clock::now()>end)return false;std::this_thread::sleep_for(std::chrono::milliseconds(1));}events.at(e).wait_and_throw();return true;}
 void synchronize()override{q->wait_and_throw();}
 void clear_events()override{events.clear();}
 void close_queue()override{q.reset();}
 void close_context()override{c.reset();context=nullptr;device=nullptr;}
};
int main(int argc,char**argv){
 auto start=Clock::now();std::filesystem::path out;size_t card=0;int seconds=50;bool authorized=false;
 for(int i=1;i<argc;i++){std::string a=argv[i];if(a=="--authorized-device-window")authorized=true;else if(a=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(a=="--output"&&i+1<argc)out=argv[++i];else if(a=="--seconds"&&i+1<argc)seconds=std::stoi(argv[++i]);else return 64;}
 if(!authorized||out.empty()||seconds<1||seconds>50)return 64;std::signal(SIGTERM,signal_stop);std::signal(SIGINT,signal_stop);
 std::ofstream rows(out/"rows.jsonl");if(!rows)return 73;
 try{
  ownrt::Device owner(std::make_unique<Backend>(card,start+std::chrono::seconds(seconds),std::filesystem::path(argv[0]).parent_path()/"raw.spv"));
  std::vector<ownrt::Allocation> bindings;for(int i=0;i<17;i++)bindings.push_back(owner.arena.allocate("arg"+std::to_string(i),5120,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction));
  // CPU storage remains alive through the explicitly waited upload.
  std::array<uint16_t,2560> initial{};initial.fill(0x3a80);
  auto host=owner.arena.allocate("initial",5120,ownrt::Memory::shadow,ownrt::Category::host_shadow,ownrt::Lifetime::process);
  std::memcpy(owner.arena.row(host).pointer,initial.data(),5120);ownrt::CopyEngine copies(owner);for(auto b:bindings){auto e=copies.copy(b,0,host,0,5120,{});if(!owner.wait(e,std::chrono::milliseconds(900)))ownrt::hold_for_supervisor();}
  int count=0;bool passed=true;std::string failure;
  for(auto method:{"explicit_in_order","explicit_out_of_order","explicit_wait_each","implicit_in_order","discard_in_order","graph","raw_regular","raw_immediate","fusion8"})for(int kind:{0,1})for(int n:{100,1000,4000}){
   if(stopped||Clock::now()>start+std::chrono::seconds(seconds)){passed=false;failure="deadline before full matrix";break;}
   Trial t;t.method=method;t.n=n;t.kind=kind;t.rows=&rows;bool available=true;t.available=&available;auto e=owner.compute(t,bindings,{});if(!owner.wait(e,std::chrono::milliseconds(900)))ownrt::hold_for_supervisor();count+=5;if(!available){passed=false;failure="one or more methods unavailable on device";}
  }
  auto receipt=owner.shutdown(std::chrono::seconds(3));if(!receipt.safe_to_exit)ownrt::hold_for_supervisor();
  std::ofstream final(out/"device.json");final<<"{\"passed\":"<<(passed?"true":"false")<<",\"device_executed\":true,\"safe_to_exit\":true,\"live_bytes\":0,\"in_flight\":0,\"rows\":"<<count<<",\"expected_rows\":270,\"error\":"<<ownrt::quote(failure)<<",\"teardown\":"<<receipt.json()<<"}\n";return passed?0:75;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}
}
