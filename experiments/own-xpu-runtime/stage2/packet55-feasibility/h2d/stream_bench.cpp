// Independently authored diagnostic. Native copy-only queue + same-device SYCL compute.
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <algorithm>
#include <chrono>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>
#include <vector>
using Clock=std::chrono::steady_clock;
namespace fs=std::filesystem;
static volatile std::sig_atomic_t stopping=0;
static void stop(int){stopping=1;}
static void require(bool yes,const std::string&why){if(!yes)throw std::runtime_error(why);}
static void ze(ze_result_t r){require(r==ZE_RESULT_SUCCESS,"Level Zero failure "+std::to_string(unsigned(r)));}
static double ns(Clock::time_point a,Clock::time_point b){return std::chrono::duration<double,std::nano>(b-a).count();}
static std::string quote(const std::string&s){std::ostringstream o;o<<std::quoted(s);return o.str();}
static constexpr size_t maxbytes=10*2329600, workitems=32768;
struct NativeCopy {
 ze_context_handle_t context{};ze_device_handle_t device{};ze_command_queue_handle_t queue{};ze_command_list_handle_t list{};
 uint8_t*host{};uint8_t*dest{};uint64_t*stamp{};uint32_t ordinal=~0u;ze_device_properties_t props{};bool pending=false;
 NativeCopy(sycl::queue&q){
  context=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_context());device=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_device());
  uint32_t n=0;ze(zeDeviceGetCommandQueueGroupProperties(device,&n,nullptr));std::vector<ze_command_queue_group_properties_t> groups(n);
  for(auto&g:groups)g.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;ze(zeDeviceGetCommandQueueGroupProperties(device,&n,groups.data()));
  for(uint32_t i=0;i<n;++i)if((groups[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COPY)&&!(groups[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE)&&groups[i].numQueues){ordinal=i;break;}
  require(ordinal!=~0u,"no copy-only engine group: refuse compute-queue fallback");
  ze_command_queue_desc_t qd{};qd.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;qd.ordinal=ordinal;qd.index=0;qd.mode=ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS;ze(zeCommandQueueCreate(context,device,&qd,&queue));
  ze_command_list_desc_t ld{};ld.stype=ZE_STRUCTURE_TYPE_COMMAND_LIST_DESC;ld.commandQueueGroupOrdinal=ordinal;ze(zeCommandListCreate(context,device,&ld,&list));
  ze_host_mem_alloc_desc_t hd{};hd.stype=ZE_STRUCTURE_TYPE_HOST_MEM_ALLOC_DESC;ze(zeMemAllocHost(context,&hd,maxbytes,4096,reinterpret_cast<void**>(&host)));
  ze_device_mem_alloc_desc_t dd{};dd.stype=ZE_STRUCTURE_TYPE_DEVICE_MEM_ALLOC_DESC;ze(zeMemAllocDevice(context,&dd,maxbytes,4096,device,reinterpret_cast<void**>(&dest)));
  ze(zeMemAllocHost(context,&hd,4096,4096,reinterpret_cast<void**>(&stamp)));
  props.stype=ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;ze(zeDeviceGetProperties(device,&props));require(props.timerResolution&&props.timestampValidBits,"invalid timestamp properties");
 }
 // All normal teardown occurs only after both queues drain. On errors main retains this owner.
 void destroy(){require(!pending,"cannot destroy pending copy");ze(zeCommandListDestroy(list));ze(zeCommandQueueDestroy(queue));ze(zeMemFree(context,host));ze(zeMemFree(context,dest));ze(zeMemFree(context,stamp));}
 void prepare(int batch,bool per_slab,size_t slab){
  ze(zeCommandListReset(list));stamp[0]=stamp[1]=0;
  ze(zeCommandListAppendWriteGlobalTimestamp(list,stamp,nullptr,0,nullptr));ze(zeCommandListAppendBarrier(list,nullptr,0,nullptr));
  if(per_slab){for(int s=0;s<batch;++s)ze(zeCommandListAppendMemoryCopy(list,dest+s*slab,host+s*slab,slab,nullptr,0,nullptr));}
  else ze(zeCommandListAppendMemoryCopy(list,dest,host,batch*slab,nullptr,0,nullptr));
  ze(zeCommandListAppendBarrier(list,nullptr,0,nullptr));ze(zeCommandListAppendWriteGlobalTimestamp(list,stamp+1,nullptr,0,nullptr));ze(zeCommandListClose(list));
 }
 void submit(){pending=true;ze(zeCommandQueueExecuteCommandLists(queue,1,&list,nullptr));}
 void wait(){for(;;){auto r=zeCommandQueueSynchronize(queue,1000000);if(r==ZE_RESULT_SUCCESS){pending=false;return;}if(r!=ZE_RESULT_NOT_READY)ze(r);}}
 double device_ns(){uint64_t mask=props.timestampValidBits>=64?~uint64_t(0):(uint64_t(1)<<props.timestampValidBits)-1;auto ticks=(stamp[1]-stamp[0])&mask;require(ticks>0,"empty device copy envelope");return double(ticks)*props.timerResolution;}
};
static sycl::event compute(sycl::queue&q,float*out){return q.parallel_for(sycl::range<1>(workitems),[=](sycl::id<1>i){float x=1.f+float(i[0]%31)/32.f,y=0.5f;for(int k=0;k<2048;++k){x=x*0.99991f+0.00011f;y=y*0.99987f+x*0.00013f;}out[i]=x+y;});}
int main(int argc,char**argv){
 fs::path output;int card=-1;bool authorized=false;std::string error,pci;sycl::queue*q=nullptr;NativeCopy*c=nullptr;float*work=nullptr;bool pending_compute=false,safe=true;size_t rows=0;
 try{
  for(int i=1;i<argc;++i){std::string k=argv[i];auto val=[&]{require(++i<argc,"missing value");return std::string(argv[i]);};if(k=="--card")card=std::stoi(val());else if(k=="--output")output=val();else if(k=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown argument "+k);}
  require(authorized&&(card==2||card==3)&&!output.empty(),"authorized card 2 or 3 required");
  require(getenv("ONEAPI_DEVICE_SELECTOR")&&std::string(getenv("ONEAPI_DEVICE_SELECTOR"))=="level_zero:"+std::to_string(card),"exact Level Zero selector required");
  require(!fs::exists(output),"native output already exists");fs::create_directories(output);std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
  q=new sycl::queue(sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  require(q->get_device().get_info<sycl::info::device::name>().find("B70")!=std::string::npos,"B70 required");
  ze_pci_ext_properties_t p{};p.stype=ZE_STRUCTURE_TYPE_PCI_EXT_PROPERTIES;ze(zeDevicePciGetPropertiesExt(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q->get_device()),&p));std::ostringstream addr;addr<<std::hex<<std::setfill('0')<<std::setw(4)<<p.address.domain<<':'<<std::setw(2)<<p.address.bus<<':'<<std::setw(2)<<p.address.device<<'.'<<p.address.function;pci=addr.str();require(pci==(card==2?"0000:43:00.0":"0000:47:00.0"),"physical PCI identity differs from coordinator card");
  c=new NativeCopy(*q);work=sycl::malloc_device<float>(workitems,*q);require(work,"compute allocation");
  std::ofstream meta(output/"metadata.json");meta<<"{\"schema\":\"ownrt.packet55.h2d.v1\",\"card\":"<<card<<",\"pci_bdf\":"<<quote(pci)<<",\"copy_only_ordinal\":"<<c->ordinal<<",\"copy_queue_index\":0,\"pinned_host_bytes\":"<<maxbytes+4096<<",\"device_bytes\":"<<maxbytes+workitems*4<<",\"pageable_verification_bytes\":"<<maxbytes<<",\"slab_bytes\":[1971200,2329600]"<<",\"timer_resolution_ns\":"<<c->props.timerResolution<<",\"timestamp_valid_bits\":"<<c->props.timestampValidBits<<",\"compute_work_items\":"<<workitems<<",\"compute_iterations\":2048,\"model_speed_claim\":false}\n";meta.close();
  std::vector<uint8_t> verify(maxbytes);std::ofstream out(output/"iterations.jsonl");out<<std::setprecision(17);require(bool(out),"output stream");
  // Warm compiled compute once. Byte patterns are changed for every measured transfer.
  pending_compute=true;compute(*q,work).wait_and_throw();pending_compute=false;
  for(size_t slab:{size_t(1971200),size_t(2329600)})for(int batch=4;batch<=10;++batch)for(bool separate:{false,true})for(int iteration=-3;iteration<30;++iteration){
   require(!stopping,"cooperative stop between bounded trials");
   // Alternate ordering; compare standalone and simultaneous trials under the same payload.
   for(int phase=0;phase<3;++phase){int mode=(phase+iteration+3)%3;const char*name=mode==0?"copy":mode==1?"compute":"concurrent";size_t bytes=batch*slab;uint8_t pattern=uint8_t(17+batch*13+iteration*7+phase);
    std::fill_n(c->host,bytes,pattern);q->memset(c->dest,pattern^255,bytes).wait_and_throw();
    auto route_known=Clock::now();if(mode!=1)c->prepare(batch,separate,slab);auto prepared=Clock::now();sycl::event event;
    auto issue=Clock::now();if(mode!=0){pending_compute=true;event=compute(*q,work);}if(mode!=1)c->submit();
    auto issued=Clock::now();double resident_ns=0;if(mode!=1){c->wait();resident_ns=ns(route_known,Clock::now());}if(mode!=0){event.wait_and_throw();pending_compute=false;}auto complete=Clock::now();
    double compute_ns=0;if(mode!=0){auto start=event.get_profiling_info<sycl::info::event_profiling::command_start>(),end=event.get_profiling_info<sycl::info::event_profiling::command_end>();require(end>start,"empty compute event");compute_ns=end-start;}
    if(mode!=1){q->memcpy(verify.data(),c->dest,bytes).wait_and_throw();require(std::all_of(verify.begin(),verify.begin()+bytes,[=](uint8_t x){return x==pattern;}),"copied payload mismatch");}
    // Compute checksum readback prevents a no-op workload; it is not a model arithmetic gate.
    float value=0;if(mode!=0){q->memcpy(&value,work,4).wait_and_throw();require(value>0.f&&value<5.f,"compute result invalid");}
    out<<"{\"slab_bytes\":"<<slab<<",\"batch\":"<<batch<<",\"copy_shape\":"<<quote(separate?"slab_commands":"contiguous_batch")<<",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<0?"true":"false")<<",\"mode\":"<<quote(name)<<",\"bytes\":"<<(mode==1?0:bytes)<<",\"route_to_resident_ns\":"<<resident_ns<<",\"list_prepare_ns\":"<<ns(route_known,prepared)<<",\"issue_ns\":"<<ns(issue,issued)<<",\"wall_ns\":"<<ns(issue,complete)<<",\"copy_device_envelope_ns\":"<<(mode==1?0:c->device_ns())<<",\"compute_event_ns\":"<<compute_ns<<",\"payload_verified\":true}\n";out.flush();require(bool(out),"output write");++rows;
   }
  }
  q->wait_and_throw();sycl::free(work,*q);work=nullptr;c->destroy();delete c;c=nullptr;delete q;q=nullptr;
 }catch(const std::exception&e){error=e.what();safe=!pending_compute&&(!c||!c->pending);if(q){try{q->wait_and_throw();}catch(...){safe=false;}}}
 // Never destroy a queue or exit while known work is outstanding after a fault.
 if(!safe){std::cerr<<"retaining uncertain device owner for coordinator: "<<error<<std::endl;for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));}
 if(!output.empty()&&fs::exists(output)){std::ofstream receipt(output/"receipt.json");receipt<<"{\"passed\":"<<(error.empty()?"true":"false")<<",\"safe_to_exit\":true,\"rows\":"<<rows<<",\"error\":"<<quote(error)<<"}\n";}
 if(!error.empty())std::cerr<<error<<'\n';return error.empty()?0:1;
}
