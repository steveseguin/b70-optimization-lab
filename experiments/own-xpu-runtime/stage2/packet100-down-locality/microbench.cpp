// Coordinator-owned diagnostic only. Full banks; receipt-bound routes supplied
// by run_micro.py after its SHA256 checks. Timings use actual shipped kernels.
#include "p100_down.hpp"
#include <csignal>
#include <atomic>
#include <iostream>
#include <fstream>
#include <chrono>
#include <iomanip>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
struct Buffers{sycl::queue&q;std::vector<void*> values;~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto p:values)sycl::free(p,q);}void*alloc(size_t bytes){auto*p=sycl::malloc_device(bytes,q);if(!p)throw std::bad_alloc();values.push_back(p);return p;}};
template<unsigned Mode>sycl::event fp32(sycl::queue&q,const uint8_t*w,const uint16_t*x,const iq3::Route*routes,float*y){return q.submit([&](sycl::handler&h){h.parallel_for(sycl::nd_range<1>(size_t(800)*64,64),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),physical=lane%2,sub=it.get_local_linear_id()/32,group=it.get_group_linear_id();
 if constexpr(Mode==1)group=p100::Kernel<1>::mapped_group(group,2560,10);
 unsigned logical=(group*2+sub)*16+lane/2,slot=logical/2560,row=logical%2560;size_t source=size_t(routes[slot].expert_id)*2560+routes[slot].row_begin+row;
 auto chains=[&]{if constexpr(Mode==2)return p100::tile_chains(w,source,x+slot*640,physical);else return p65::wide_chains<iq3::Type::IQ4_NL,640,16>(w+source*360,x+slot*640,physical);}();
 float v=p49dvirtual::local_tree<16>(chains),rhs=sycl::select_from_group(sg,v,(lane+1)%32);if(!physical)y[logical]=v+rhs;
 });});}
int main(int argc,char**argv){try{
 if(argc!=3||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("coordinator admission and route payload required");
 std::ifstream input(argv[2],std::ios::binary);std::vector<uint8_t> route_bytes((std::istreambuf_iterator<char>(input)),{});
 if(!input||route_bytes.empty()||route_bytes.size()%120||route_bytes.size()>120*1152)throw std::runtime_error("bounded real route payload required");
 std::vector<iq3::Route> host_routes(route_bytes.size()/12);std::memcpy(host_routes.data(),route_bytes.data(),route_bytes.size());
 for(auto r:host_routes)if(r.expert_id>=512||r.row_begin!=0||r.row_count!=2560)throw std::runtime_error("full real route shape required");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 constexpr unsigned rows=2560,K=640,count=10;constexpr size_t bank_bytes=size_t(512)*rows*360,scrub_words=size_t(128)*1024*1024; // 512 MiB
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});
 {Buffers b{q,{}};auto*w=(uint8_t*)b.alloc(bank_bytes);auto*t=(uint8_t*)b.alloc(bank_bytes);auto*x=(uint16_t*)b.alloc(K*count*2);auto*routes=(iq3::Route*)b.alloc(120);auto*y=(uint16_t*)b.alloc(rows*count*2);auto*status=(uint32_t*)b.alloc(count*4);auto*control=(uint32_t*)b.alloc(12);auto*f=(float*)b.alloc(rows*count*4);auto*scrub=(uint32_t*)b.alloc(scrub_words*4);
 uint32_t seed=100;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
 std::vector<uint16_t>hx(K*count);for(auto&v:hx)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);q.memcpy(x,hx.data(),hx.size()*2).wait_and_throw();
 for(unsigned first=0;first<512*rows;first+=256){guard();std::vector<uint8_t>raw(256*360),packed(raw.size());for(auto&v:raw)v=next()>>24;
  for(unsigned row=0;row<256;++row){for(unsigned block=0;block<20;++block){uint16_t h=0x2400+next()%1024;std::memcpy(raw.data()+row*360+block*18,&h,2);}p49bgemv::repack_row(iq3::Type::IQ4_NL,K,raw.data()+row*360,packed.data()+row*360);}
  auto trans=p100::transpose(packed.data(),256);q.memcpy(w+size_t(first)*360,packed.data(),packed.size()).wait_and_throw();q.memcpy(t+size_t(first)*360,trans.data(),trans.size()).wait_and_throw();
 }
 uint32_t controls[3]={0,1,0};q.memcpy(control,controls,12).wait_and_throw();
 p65::Kernel<iq3::Type::IQ4_NL,640,64,false,true>prod;p100::Kernel<1>interleave;p100::Kernel<2>tile;
 std::array<void*,19>pp{};pp[0]=w;pp[1]=w;pp[2]=x;pp[3]=y;pp[4]=y;pp[5]=routes;pp[6]=status;pp[7]=status;pp[16]=control;pp[17]=control+1;pp[18]=control+2;auto tp=pp;tp[0]=t;tp[1]=t;
 auto launch=[&](unsigned mode){return mode==0?prod.submit(q,pp,{}):mode==1?interleave.submit(q,pp,{}):tile.submit(q,tp,{});};
 auto cold=[&]{q.parallel_for(sycl::range<1>(scrub_words),[=](sycl::id<1>id){scrub[id]=uint32_t(id[0]);}).wait_and_throw();};
 std::vector<float>expected(rows*count),actual(expected.size());std::vector<uint16_t>ey(rows*count),ay(ey.size());std::vector<uint32_t>hs(count);
 const unsigned route_count=host_routes.size()/10;
 for(unsigned ri=0;ri<route_count;++ri){guard();q.memcpy(routes,host_routes.data()+ri*10,120).wait_and_throw();
  fp32<0>(q,w,x,routes,f).wait_and_throw();launch(0).wait_and_throw();q.memcpy(expected.data(),f,expected.size()*4).wait_and_throw();q.memcpy(ey.data(),y,ey.size()*2).wait_and_throw();
  for(unsigned mode=1;mode<=2;++mode){const char*name=mode==1?"down-interleave":"down-tile16";
   if(mode==1)fp32<1>(q,w,x,routes,f).wait_and_throw();else fp32<2>(q,t,x,routes,f).wait_and_throw();launch(mode).wait_and_throw();q.memcpy(actual.data(),f,actual.size()*4).wait_and_throw();q.memcpy(ay.data(),y,ay.size()*2).wait_and_throw();q.memcpy(hs.data(),status,count*4).wait_and_throw();q.memcpy(controls,control,12).wait_and_throw();
   if(std::memcmp(expected.data(),actual.data(),expected.size()*4)||ey!=ay||controls[0]||controls[1]!=1||controls[2]||std::any_of(hs.begin(),hs.end(),[](auto v){return v!=0;}))throw std::runtime_error("device FP32/BF16/status mismatch");
   std::cout<<"{\"kind\":\"correctness\",\"view\":\""<<name<<"\",\"route\":"<<ri<<",\"fp32_exact\":true,\"bf16_exact\":true,\"status_exact\":true,\"rows\":2560,\"columns\":640,\"count\":10,\"experts\":512}\n";
   for(unsigned rep=0;rep<40;++rep)for(unsigned pos=0;pos<2;++pos){guard();unsigned arm=(pos^(rep&1))?mode:0;cold();auto event=launch(arm);event.wait_and_throw();auto ns=event.get_profiling_info<sycl::info::event_profiling::command_end>()-event.get_profiling_info<sycl::info::event_profiling::command_start>();
    std::cout<<"{\"kind\":\"sample\",\"pair\":\""<<name<<"\",\"view\":\""<<(arm?name:"production")<<"\",\"route\":"<<ri<<",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"event_ns\":"<<ns<<",\"rows\":2560,\"columns\":640,\"count\":10,\"experts\":512,\"wg\":64,\"sg\":32,\"scrub_bytes\":536870912,\"diagnostic_only\":true}\n";
   }std::cout<<std::flush;
  }
 }q.wait_and_throw();guard();
 std::cout<<"{\"kind\":\"native_complete\",\"route_count\":"<<route_count<<"}\n"<<std::flush;
 }
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"rows\":2560,\"columns\":640,\"count\":10,\"experts\":512,\"route_count\":"<<host_routes.size()/10<<",\"diagnostic_only\":true}\n"<<std::flush;return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
