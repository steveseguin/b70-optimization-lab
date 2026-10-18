// Independently authored transport harness, unchanged lab expert arithmetic.
#include "../packet58j-onecard-port/p49d_expert.hpp"
#include "../packet58j-onecard-port/p100_down.hpp"
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <atomic>
#include <csignal>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <memory>
#include <thread>
#include <set>
namespace ownrt {uint64_t next_handle(){static std::atomic<uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void check(bool b,const char*s){if(!b)throw std::runtime_error(s);}
static void guard(){check(!stopped,"cooperative stop");}
static void zecheck(ze_result_t r){check(r==ZE_RESULT_SUCCESS,"Level Zero copy engine operation failed");}
using Clock=std::chrono::steady_clock;
static double elapsed(Clock::time_point t){return std::chrono::duration<double,std::nano>(Clock::now()-t).count();}
#include "micro_common.hpp"
struct Queues {
 sycl::queue q;ze_command_list_handle_t list=nullptr;std::unique_ptr<sycl::queue> copy;
 std::vector<void*> memory;
 Queues():q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}){
  auto dev=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_device());
  auto ctx=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_context());
  uint32_t n=0;zecheck(zeDeviceGetCommandQueueGroupProperties(dev,&n,nullptr));
  std::vector<ze_command_queue_group_properties_t> groups(n);for(auto&g:groups)g.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;
  zecheck(zeDeviceGetCommandQueueGroupProperties(dev,&n,groups.data()));uint32_t ord=~0u;
  for(unsigned i=0;i<n;++i)if((groups[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COPY)&&!(groups[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE)&&groups[i].numQueues){ord=i;break;}
  check(ord!=~0u,"dedicated copy-only group required");ze_command_queue_desc_t cd{};cd.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;cd.ordinal=ord;cd.flags=ZE_COMMAND_QUEUE_FLAG_IN_ORDER;cd.mode=ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS;
  zecheck(zeCommandListCreateImmediate(ctx,dev,&cd,&list));
  copy=std::make_unique<sycl::queue>(sycl::make_queue<sycl::backend::ext_oneapi_level_zero>({list,q.get_device(),sycl::ext::oneapi::level_zero::ownership::keep,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}},q.get_context()));
  std::cout<<"{\"kind\":\"device\",\"copy_only_ordinal\":"<<ord<<",\"copy_index\":0,\"copy_queues_available\":"<<groups[ord].numQueues<<",\"device_name\":\""<<q.get_device().get_info<sycl::info::device::name>()<<"\"}\n";
 }
 void*alloc(size_t n,bool host=false,size_t alignment=0){void*p=host?(alignment?sycl::aligned_alloc_host(alignment,n,q):sycl::malloc_host(n,q)):sycl::malloc_device(n,q);check(p,"allocation failed");memory.push_back(p);return p;}
 void drain(){copy->wait();q.wait();copy->throw_asynchronous();q.throw_asynchronous();}
 ~Queues(){try{drain();}catch(...){/* Never free buffers on an unproved drain. */for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));}
  for(auto p:memory)sycl::free(p,q.get_context());copy.reset();if(list&&zeCommandListDestroy(list)!=ZE_RESULT_SUCCESS)for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));}
};
struct HostCase {size_t separate,compact,aligned,tiled;};
struct LocalDrain {Queues& o;~LocalDrain(){try{o.drain();}catch(...){for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));}}};
void bench(Queues&o,const std::vector<Case>&cases,unsigned owner){
 auto&q=o.q;auto&cq=*o.copy;std::vector<HostCase> offsets;size_t separate_n=0,compact_n=0,aligned_n=0,tile_n=0;
 for(auto&c:cases){offsets.push_back({separate_n,compact_n,aligned_n,tile_n});size_t n=misses(c),g=gate_bytes(c),e=2*g+DOWN;separate_n+=n*e;compact_n+=n*align_up(e+64);aligned_n+=n*align_up(e);tile_n+=n*DOWN;}
 size_t pinned=separate_n+compact_n+aligned_n+tile_n+4*ALIGN+120;
 check(pinned<7ull*1024*1024*1024,"pinned allocation budget");
 auto*host=(uint8_t*)o.alloc(separate_n+ALIGN,true);auto*compact=(uint8_t*)o.alloc(compact_n+ALIGN,true,ALIGN);
 auto*aligned=(uint8_t*)o.alloc(aligned_n+ALIGN,true,ALIGN);auto*tile=(uint8_t*)o.alloc(tile_n+ALIGN,true);
 auto*route_back=(iq3::Route*)o.alloc(120,true);
 // Distinct regions for every route case. Only identical immutable weights are reused
 // across arms, always after a 512MiB device cache scrub; no warmed small-slab loop.
 std::cout<<"{\"kind\":\"allocation\",\"pinned_bytes\":"<<pinned<<",\"host_mod64k\":"<<uintptr_t(host)%ALIGN<<",\"compact_mod64k\":"<<uintptr_t(compact+64)%ALIGN<<",\"aligned_mod64k\":"<<uintptr_t(aligned)%ALIGN<<",\"scrub_bytes\":"<<SCRUB<<"}\n";
 auto*device=(uint8_t*)o.alloc(10*2329600ull);auto*down_tile=(uint8_t*)o.alloc(10*DOWN);
 auto*gp=(p58::Pointer*)o.alloc(512*sizeof(p58::Pointer));auto*up=(p58::Pointer*)o.alloc(512*sizeof(p58::Pointer));auto*dp=(p58::Pointer*)o.alloc(512*sizeof(p58::Pointer));
 auto*x=(uint16_t*)o.alloc(5120);auto*y=(uint16_t*)o.alloc(12800);auto*uy=(uint16_t*)o.alloc(12800);auto*act=(uint16_t*)o.alloc(12800);auto*dy=(uint16_t*)o.alloc(51200);
 auto*gr=(iq3::Route*)o.alloc(120);auto*dr=(iq3::Route*)o.alloc(120);auto*status=(uint32_t*)o.alloc(132);
 auto*scrub=(uint32_t*)o.alloc(SCRUB);auto*sink=(uint32_t*)o.alloc(65536*4);
 q.memset(scrub,0x6d,SCRUB).wait_and_throw();
 auto evict=[&]{q.parallel_for(sycl::range<1>(65536),[=](sycl::id<1>i){uint32_t v=0;for(size_t j=i[0];j<SCRUB/64;j+=65536)v^=scrub[j*16];sink[i]=v;}).wait_and_throw();};
 std::vector<uint16_t> hx(2560);for(unsigned i=0;i<hx.size();++i)hx[i]=iq3::bf16_bits(float(int(i%63)-31)/32.f);q.memcpy(x,hx.data(),5120).wait_and_throw();
 std::array<void*,19> gb{},db{};gb[0]=gp;gb[1]=up;gb[2]=x;gb[3]=y;gb[4]=uy;gb[5]=gr;gb[6]=status;gb[7]=status+10;
 db[0]=dp;db[1]=dp;db[2]=act;db[3]=dy;db[4]=dy;db[5]=dr;db[6]=status+20;
 for(auto*b:{&gb,&db}){(*b)[16]=status+30;(*b)[17]=status+31;(*b)[18]=status+32;}
 p49dvirtual::GateKernel gate;gate.indirect=true;p49dvirtual::DownKernel down;down.indirect=true;p100::Kernel<2> tiled;tiled.indirect=true;
 p28::Kernel<iq3::Type::IQ3_S,2560,1,1,false,true> iq3gate;iq3gate.b.rb=1100;iq3gate.b.rows=640;iq3gate.b.count=10;iq3gate.b.experts=512;iq3gate.b.indirect=true;iq3gate.b.has_routes=true;
 auto poison=[&]{q.memset(y,0xa5,12800);q.memset(uy,0xa5,12800);q.memset(act,0xa5,12800);q.memset(dy,0xa5,51200);q.memset(status,0,132);uint32_t one=1;q.memcpy(status+31,&one,4).wait_and_throw();};
 auto output=[&]{std::vector<uint8_t> out(12800*3+51200+132);size_t off=0;for(auto pair:{std::pair<void*,size_t>{y,12800},{uy,12800},{act,12800},{dy,51200},{status,132}}){q.memcpy(out.data()+off,pair.first,pair.second).wait_and_throw();off+=pair.second;}return out;};
 auto launch_gate=[&](const Case&c,const std::vector<sycl::event>&deps){return c.layer==2?iq3gate.submit(q,gb,deps):gate.submit(q,gb,deps);};
 auto activation=[&](sycl::event g){return q.submit([&](sycl::handler&h){h.depends_on(g);h.parallel_for(sycl::range<1>(6400),[=](sycl::id<1>i){act[i]=p39::activation(y[i],uy[i]);});});};
 for(unsigned ci=0;ci<cases.size();++ci){guard();auto&c=cases[ci];auto off=offsets[ci];size_t g=gate_bytes(c),e=2*g+DOWN,n=misses(c);
  std::vector<uint8_t> all(10*e),tiles(10*DOWN);LocalDrain case_drain{o};unsigned mi=0;
  for(unsigned s=0;s<10;++s){unsigned seed=125+c.layer*65537+c.routes[s].expert_id*17;auto a=fixture(c.layer==2?iq3::Type::IQ3_S:iq3::Type::IQ2_S,640,2560,seed);auto b=fixture(c.layer==2?iq3::Type::IQ3_S:iq3::Type::IQ2_S,640,2560,seed+1);auto d=fixture(iq3::Type::IQ4_NL,2560,640,seed+2);auto td=p100::transpose(d.data(),2560);
   std::memcpy(all.data()+s*e,a.data(),g);std::memcpy(all.data()+s*e+g,b.data(),g);std::memcpy(all.data()+s*e+2*g,d.data(),DOWN);std::memcpy(tiles.data()+s*DOWN,td.data(),DOWN);
   if(c.mask&(1u<<s)){std::memcpy(host+off.separate+mi*g,a.data(),g);std::memcpy(host+off.separate+n*g+mi*g,b.data(),g);std::memcpy(host+off.separate+2*n*g+mi*DOWN,d.data(),DOWN);
    std::memcpy(compact+off.compact+mi*align_up(e+64)+64,all.data()+s*e,e);std::memcpy(aligned+off.aligned+mi*align_up(e),all.data()+s*e,e);std::memcpy(tile+off.tiled+mi*DOWN,td.data(),DOWN);++mi;}}
  q.memcpy(device,all.data(),all.size());q.memcpy(down_tile,tiles.data(),tiles.size());
  std::array<iq3::Route,10> hr;for(unsigned s=0;s<10;++s){hr[s]=c.routes[s];hr[s].row_count=640;}q.memcpy(gr,hr.data(),120);q.memcpy(dr,c.routes,120).wait_and_throw();
  auto tables=[&](unsigned mode){std::array<p58::Pointer,512> a{},b{},d{};LocalDrain tables_drain{o};unsigned m=0;
   for(unsigned s=0;s<10;++s){auto id=c.routes[s].expert_id;bool miss=c.mask&(1u<<s);auto*aa=device+s*e;auto*bb=aa+g;auto*dd=aa+2*g;
    if(mode<2&&miss){aa=host+off.separate+m*g;bb=host+off.separate+n*g+m*g;dd=mode==1?tile+off.tiled+m*DOWN:host+off.separate+2*n*g+m*DOWN;}
    else if(mode==1)dd=down_tile+s*DOWN;
    a[id]={uintptr_t(aa),1};b[id]={uintptr_t(bb),1};d[id]={uintptr_t(dd),1};if(miss)++m;}
   q.memcpy(gp,a.data(),sizeof(a));q.memcpy(up,b.data(),sizeof(b));q.memcpy(dp,d.data(),sizeof(d)).wait_and_throw();};
  tables(2);poison();auto eg=launch_gate(c,{});auto ea=activation(eg);down.submit(q,db,{ea}).wait_and_throw();auto expected=output();
  // Reverse all alternatives in the second fresh process; no favorable retry.
  for(unsigned index=0;index<7;++index){guard();unsigned mode=owner==1?index:6-index;tables(mode);poison();
   if(mode>=2)for(unsigned s=0;s<10;++s)if(c.mask&(1u<<s))q.memset(device+s*e,0xa5,e);
   q.wait_and_throw();evict();std::vector<sycl::event>copies,gate_ready,down_ready;double copy_wait=0,route_ns=0;auto start=Clock::now();
   if(mode>=2){auto t=Clock::now();cq.memcpy(route_back,dr,120).wait_and_throw();route_ns=elapsed(t);check(std::memcmp(route_back,c.routes,120)==0,"route readback differs");
    unsigned m=0;auto copy_one=[&](void*dst,const void*src,size_t bytes){auto ev=cq.memcpy(dst,src,bytes);copies.push_back(ev);if(mode==2){auto w=Clock::now();ev.wait_and_throw();copy_wait+=elapsed(w);}return ev;};
    if(mode==6){for(unsigned s=0;s<10;++s)if(c.mask&(1u<<s)){copy_one(device+s*e,host+off.separate+m*g,g);gate_ready={copy_one(device+s*e+g,host+off.separate+n*g+m*g,g)};++m;}}
    else {for(unsigned s=0;s<10;++s)if(c.mask&(1u<<s)){
      if(mode==4||mode==5)copy_one(device+s*e,mode==4?compact+off.compact+m*align_up(e+64)+64:aligned+off.aligned+m*align_up(e),e);
      else {copy_one(device+s*e,host+off.separate+m*g,g);copy_one(device+s*e+g,host+off.separate+n*g+m*g,g);copy_one(device+s*e+2*g,host+off.separate+2*n*g+m*DOWN,DOWN);}++m;}
     if(!copies.empty())gate_ready={copies.back()};}
   }
   auto ge=launch_gate(c,gate_ready);
   if(mode==6){unsigned m=0;for(unsigned s=0;s<10;++s)if(c.mask&(1u<<s)){copies.push_back(cq.memcpy(device+s*e+2*g,host+off.separate+2*n*g+m*DOWN,DOWN));++m;}if(!copies.empty())down_ready={copies.back()};}
   auto ae=activation(ge);down_ready.push_back(ae);auto de=mode==1?tiled.submit(q,db,down_ready):down.submit(q,db,down_ready);de.wait_and_throw();double wall=elapsed(start);
   check(output()==expected,"expert gate/up/activation/down/status bytes differ from production resident oracle");
   size_t verified=0;if(mode>=2){std::vector<uint8_t> bytes(e);for(unsigned s=0;s<10;++s)if(c.mask&(1u<<s)){q.memcpy(bytes.data(),device+s*e,e).wait_and_throw();check(std::memcmp(bytes.data(),all.data()+s*e,e)==0,"delivered packed expert bytes differ");verified+=e;}}
   auto event_ns=[](const sycl::event&ev){return ev.get_profiling_info<sycl::info::event_profiling::command_end>()-ev.get_profiling_info<sycl::info::event_profiling::command_start>();};
   uint64_t copy_sum=0,copy_first=0,copy_last=0,down_copy_first=0;for(unsigned j=0;j<copies.size();++j){auto&ev=copies[j];ev.wait_and_throw();copy_sum+=event_ns(ev);
    auto st=ev.get_profiling_info<sycl::info::event_profiling::command_start>();auto en=ev.get_profiling_info<sycl::info::event_profiling::command_end>();if(!j)copy_first=st;copy_last=en;if(mode==6&&j==2*n)down_copy_first=st;}
   auto gate_start=ge.get_profiling_info<sycl::info::event_profiling::command_start>();auto activation_end=ae.get_profiling_info<sycl::info::event_profiling::command_end>();
   uint64_t overlap=mode==6&&n&&std::min(copy_last,activation_end)>std::max(down_copy_first,gate_start)?std::min(copy_last,activation_end)-std::max(down_copy_first,gate_start):0;
   std::cout<<std::setprecision(17)<<"{\"kind\":\"sample\",\"case\":"<<ci<<",\"token\":"<<c.token<<",\"layer\":"<<c.layer<<",\"mask\":"<<c.mask<<",\"misses\":"<<n<<",\"view\":\""<<modes[mode]<<"\",\"miss_bytes\":"<<n*e<<",\"wall_ns\":"<<wall<<",\"route_readback_ns\":"<<route_ns<<",\"serial_copy_wait_ns\":"<<copy_wait<<",\"copy_events\":"<<copies.size()<<",\"copy_event_sum_ns\":"<<copy_sum<<",\"copy_first_ns\":"<<copy_first<<",\"copy_last_ns\":"<<copy_last<<",\"pipeline_envelope_overlap_ns\":"<<overlap<<",\"gate_ns\":"<<event_ns(ge)<<",\"activation_ns\":"<<event_ns(ae)<<",\"down_ns\":"<<event_ns(de)<<",\"delivered_bytes_checked\":"<<verified<<",\"all_bytes_exact\":true,\"diagnostic_only\":true}\n"<<std::flush;
  }
 }o.drain();guard();
}
int main(int argc,char**argv){try{check(argc==4&&std::string(argv[1])=="--coordinator-admitted-device-window","coordinator admission, cases and fresh owner required");unsigned owner=std::stoul(argv[3]);check(owner==1||owner==2,"fresh owner");std::ifstream in(argv[2],std::ios::binary);std::vector<Case>cases(384);in.read((char*)cases.data(),cases.size()*sizeof(Case));check(bool(in)&&in.peek()==EOF,"384 complete real-route cases required");
 for(auto&c:cases){check(c.token<128&&c.layer<48&&c.mask<1024,"case bounds");std::set<unsigned> ids;for(auto r:c.routes){check(r.expert_id<512&&!r.row_begin&&r.row_count==2560,"route bounds");ids.insert(r.expert_id);}check(ids.size()==10,"ten distinct experts");}
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);{Queues q;bench(q,cases,owner);}std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"cases\":384,\"samples\":2688,\"model_loaded\":false,\"diagnostic_only\":true}\n"<<std::flush;return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
