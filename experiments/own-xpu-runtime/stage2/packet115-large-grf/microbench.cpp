// Coordinator-only real-route diagnostic. Kernels reside in the two AOT images.
#include "../packet103-record-bundle/p90_layout.hpp"
#include "../packet103-record-bundle/p100_down.hpp"
#include "expert_image.hpp"
#include <atomic>
#include <csignal>
#include <fstream>
#include <iostream>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
struct Buffers{
 sycl::queue&q;std::vector<void*>values;
 ~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto p:values)sycl::free(p,q);}
 void*alloc(size_t n){auto*p=sycl::malloc_device(n,q);if(!p)throw std::bad_alloc();values.push_back(p);return p;}
};
const char*names[]={"production","e3-next","iq4-bytepair","v4-batch2-shared","e5-shared"};
void bench(sycl::queue&q,const std::vector<iq3::Route>&captured,bool down){
 const unsigned rows=down?2560:640,K=down?640:2560,count=10,experts=512;
 const size_t stride=down?360:840,bankbytes=size_t(experts)*rows*stride;
 Buffers b{q,{}};auto*w=(uint8_t*)b.alloc(bankbytes);auto*up=down?w:(uint8_t*)b.alloc(bankbytes);
 auto*x=(uint16_t*)b.alloc(size_t(K)*(down?count:1)*2);auto*y=b.alloc(rows*count*2);auto*py=down?y:b.alloc(rows*count*2);
 auto*route=(iq3::Route*)b.alloc(120);auto*status=b.alloc(count*4);auto*ps=down?status:b.alloc(count*4);auto*control=(uint32_t*)b.alloc(12);
 constexpr size_t scrub_bytes=536870912;auto*scrub=b.alloc(scrub_bytes);
 uint32_t seed=115;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
 const auto type=down?iq3::Type::IQ4_NL:iq3::Type::IQ2_S;const auto rawstride=p49bgemv::source_row_bytes(type,K);const auto block=iq3::layout(type);
 for(unsigned stream=0;stream<(down?1u:2u);++stream)for(unsigned first=0;first<experts*rows;first+=256){
  guard();std::vector<uint8_t>raw(rawstride),packed(256*stride);
  for(unsigned r=0;r<256;++r){for(auto&v:raw)v=next()>>24;for(size_t at=0;at<raw.size();at+=block.bytes){uint16_t h=0x2400+next()%1024;std::memcpy(raw.data()+at,&h,2);}
   if(down)p49bgemv::repack_row(type,K,raw.data(),packed.data()+r*stride);else p90::expert_repack(K,raw.data(),packed.data()+r*stride);
  }
  if(down)packed=p100::transpose(packed.data(),256);
  q.memcpy((stream?up:w)+size_t(first)*stride,packed.data(),packed.size()).wait_and_throw();
 }
 std::vector<uint16_t>hx(size_t(K)*(down?count:1));for(auto&v:hx)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);
 q.memcpy(x,hx.data(),hx.size()*2).wait_and_throw();uint32_t hc[3]={0,1,0};q.memcpy(control,hc,12).wait_and_throw();
 std::array<void*,19>p{};p[0]=w;p[1]=up;p[2]=x;p[3]=y;p[4]=py;p[5]=route;p[6]=status;p[7]=ps;p[16]=control;p[17]=control+1;p[18]=control+2;
 auto launch=[&](unsigned arm,bool large){return (large?p115_image::large:p115_image::normal)(arm,down,q,p,{},rows,count,experts);};
 auto poison=[&]{q.memset(y,0xa5,rows*count*2);if(!down)q.memset(py,0xa5,rows*count*2);q.memset(status,0xa5,count*4);if(!down)q.memset(ps,0xa5,count*4);q.memcpy(control,hc,12).wait_and_throw();};
 auto bytes=[&]{std::vector<uint8_t>v(rows*count*2*(down?1:2)+count*4*(down?1:2)+12);size_t at=0;
  auto copy=[&](void*src,size_t n){q.memcpy(v.data()+at,src,n).wait_and_throw();at+=n;};copy(y,rows*count*2);if(!down)copy(py,rows*count*2);copy(status,count*4);if(!down)copy(ps,count*4);copy(control,12);return v;};
 const unsigned vectors=captured.size()/count;
 for(unsigned ri=0;ri<vectors;++ri){
  guard();iq3::Route selected[10];for(unsigned i=0;i<count;++i){selected[i]=captured[ri*count+i];selected[i].row_count=rows;}
  q.memcpy(route,selected,120).wait_and_throw();
  poison();launch(0,false).wait_and_throw();const auto expected=bytes();
  for(unsigned arm=1;arm<5;++arm){if((arm==2)!=down)continue;
   for(unsigned comparator=0;comparator<2;++comparator){const char*controlname=comparator?"production-large":"production";
    poison();launch(0,comparator).wait_and_throw();if(bytes()!=expected)throw std::runtime_error("LARGE production output/status/control bytes differ");
    poison();launch(arm,true).wait_and_throw();if(bytes()!=expected)throw std::runtime_error("candidate output/status/control bytes differ");
    std::cout<<"{\"kind\":\"correctness\",\"view\":\""<<names[arm]<<"\",\"control\":\""<<controlname<<"\",\"route\":"<<ri<<",\"all_bytes_exact\":true,\"bf16_exact\":true,\"status_exact\":true,\"rows\":"<<rows<<",\"columns\":"<<K<<",\"count\":10,\"experts\":512}\n";
    for(unsigned rep=0;rep<2;++rep)for(unsigned pos=0;pos<2;++pos){guard();bool candidate=pos^(rep&1);
     q.memset(scrub,0x6d,scrub_bytes).wait_and_throw();auto event=launch(candidate?arm:0,candidate||comparator);event.wait_and_throw();
     auto ns=event.get_profiling_info<sycl::info::event_profiling::command_end>()-event.get_profiling_info<sycl::info::event_profiling::command_start>();
     std::cout<<"{\"kind\":\"sample\",\"pair\":\""<<names[arm]<<"\",\"control\":\""<<controlname<<"\",\"view\":\""<<(candidate?names[arm]:controlname)<<"\",\"route\":"<<ri<<",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"event_ns\":"<<ns<<",\"rows\":"<<rows<<",\"columns\":"<<K<<",\"count\":10,\"experts\":512,\"wg\":64,\"sg\":32,\"scrub_bytes\":536870912,\"diagnostic_only\":true}\n";
    }
   }
  }std::cout<<std::flush;
 }q.wait_and_throw();guard();
}
int main(int argc,char**argv){try{
 if(argc!=3||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("coordinator admission and real route payload required");
 std::ifstream in(argv[2],std::ios::binary);std::vector<uint8_t>raw((std::istreambuf_iterator<char>(in)),{});
 if(!in||raw.size()!=384*120)throw std::runtime_error("exactly384 captured real routes required");
 std::vector<iq3::Route>routes(raw.size()/12);std::memcpy(routes.data(),raw.data(),raw.size());
 for(auto r:routes)if(r.expert_id>=512||r.row_begin||r.row_count!=2560)throw std::runtime_error("captured route shape");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 {sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});bench(q,routes,false);bench(q,routes,true);q.wait_and_throw();}
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"route_count\":384,\"candidates\":[\"e3-next\",\"iq4-bytepair\",\"v4-batch2-shared\",\"e5-shared\"],\"diagnostic_only\":true}\n"<<std::flush;return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
