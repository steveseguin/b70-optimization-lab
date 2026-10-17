// Independently authored packet48 harness. Only inherited lab arithmetic is reused.
#include "gemv.hpp"
#include "../packet45-merged3/p39_fused.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "../packet45-merged3/p39_sycl.hpp"
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#endif
#include <openssl/sha.h>
#include <algorithm>
#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <thread>
namespace fs=std::filesystem;
using iq3::Type;
static volatile std::sig_atomic_t stopping=0;
static void stop(int){stopping=1;}
static void need(bool v,const char* why){if(!v)throw std::runtime_error(why);}
static std::string hash(const void* p,size_t n){unsigned char h[32];SHA256(static_cast<const unsigned char*>(p),n,h);std::ostringstream o;for(auto c:h)o<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return o.str();}
template<class T>static std::string hash(const std::vector<T>&v){return hash(v.data(),v.size()*sizeof(T));}
static uint64_t mix(uint64_t x){x^=x>>30;x*=0xbf58476d1ce4e5b9ull;x^=x>>27;x*=0x94d049bb133111ebull;return x^(x>>31);}

struct Runtime {
 bool closed=false;
 std::vector<void*> allocations;
 std::string identity="CPU mock";
#ifndef OWN_RT_HOST_ONLY
 ze_context_handle_t native=nullptr;
 std::unique_ptr<sycl::context> context;
 std::unique_ptr<sycl::queue> queue;
 Runtime(){
  std::vector<sycl::device> cards;
  for(const auto&p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)
   for(const auto&d:p.get_devices(sycl::info::device_type::gpu))cards.push_back(d);
  need(!cards.empty(),"physical card 0 missing");auto d=cards.at(0);
  need(d.get_info<sycl::ext::intel::info::device::pci_address>()=="0000:23:00.0",
       "lab physical card0 must be LevelZero0 at PCI 0000:23:00.0");
  auto sizes=d.get_info<sycl::info::device::sub_group_sizes>();
  need(std::find(sizes.begin(),sizes.end(),32)!=sizes.end(),"SG32 required");
  identity="LevelZero:0:"+d.get_info<sycl::info::device::name>()+":"+d.get_info<sycl::info::device::driver_version>()+":PCI="+d.get_info<sycl::ext::intel::info::device::pci_address>();
  auto handler=[](sycl::exception_list es){for(auto e:es)std::rethrow_exception(e);};
  ze_context_desc_t desc{};desc.stype=ZE_STRUCTURE_TYPE_CONTEXT_DESC;
  auto driver=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d.get_platform());
  need(zeContextCreate(driver,&desc,&native)==ZE_RESULT_SUCCESS,"single native context creation");
  context=std::make_unique<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>({native,{d},sycl::ext::oneapi::level_zero::ownership::keep},handler));
  queue=std::make_unique<sycl::queue>(*context,d,handler,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
 }
 void drain(){queue->wait_and_throw();}
#else
 void drain(){}
#endif
 void* alloc(size_t n){void*p=nullptr;
#ifdef OWN_RT_HOST_ONLY
  p=::operator new(n,std::align_val_t(64));
#else
  p=sycl::aligned_alloc_device(64,n,*queue);
#endif
  need(p!=nullptr,"allocation failed");allocations.push_back(p);return p;
 }
 void put(void*d,const void*s,size_t n){
#ifdef OWN_RT_HOST_ONLY
  std::memcpy(d,s,n);
#else
  // Same bounded copy policy as the runtime, no enormous single-copy command.
  for(size_t off=0;off<n;off+=64*1024*1024){size_t take=std::min(n-off,size_t(64*1024*1024));queue->memcpy(static_cast<uint8_t*>(d)+off,static_cast<const uint8_t*>(s)+off,take).wait_and_throw();}
#endif
 }
 std::vector<uint8_t> get(const void*s,size_t n){std::vector<uint8_t>v(n);
#ifdef OWN_RT_HOST_ONLY
  std::memcpy(v.data(),s,n);
#else
  queue->memcpy(v.data(),s,n).wait_and_throw();
#endif
  return v;
 }
 void release(){drain();for(void*p:allocations){
#ifdef OWN_RT_HOST_ONLY
  ::operator delete(p,std::align_val_t(64));
#else
  sycl::free(p,*context);
#endif
 }allocations.clear();}
 void close(){if(closed)return;release();
#ifndef OWN_RT_HOST_ONLY
  queue.reset();context.reset();need(zeContextDestroy(native)==ZE_RESULT_SUCCESS,"native context teardown");native=nullptr;
#endif
 closed=true;}
};

struct Timing {uint64_t start,end;};
struct Job {
 Runtime&r;Type type;unsigned k,rows,experts,count,projections;
 size_t old_stride,new_stride;
 std::array<p39::Bound,2> old{},fresh{};
 std::string input_identity;
 Job(Runtime&rt,Type t,unsigned K,unsigned N,unsigned E,unsigned P):r(rt),type(t),k(K),rows(N),experts(E),count(E==1?1:10),projections(P){
  old_stride=p48::source_row_bytes(t,k);new_stride=p48::layout(t,k).row_bytes;
  const size_t weight_rows=size_t(rows)*experts;
  auto weights=[&](unsigned seed){
   std::vector<uint8_t>raw(weight_rows*old_stride),packed(weight_rows*new_stride);
   auto fmt=iq3::layout(type);const size_t ggstride=k/fmt.elements*fmt.bytes;
   std::vector<uint8_t>row(ggstride);
   for(size_t n=0;n<weight_rows;++n){
    for(size_t j=0;j<row.size();++j)row[j]=uint8_t(mix(seed+17*n+j));
    for(size_t b=0;b<row.size();b+=fmt.bytes){size_t s=b+(type==Type::Q6_K?208:0);uint16_t scale=uint16_t(0x0800+((n+b+seed)%512));row[s]=uint8_t(scale);row[s+1]=uint8_t(scale>>8);}
    if(type==Type::Q6_K||type==Type::Q8_0){auto v=iq3::expanded::expand(type,row.data(),row.size(),k);std::memcpy(raw.data()+n*old_stride,v.data(),v.size());}
    else std::memcpy(raw.data()+n*old_stride,row.data(),row.size());
    p48::repack_row(type,k,raw.data()+n*old_stride,packed.data()+n*new_stride);
   }
   auto a=static_cast<uint8_t*>(r.alloc(raw.size())),b=static_cast<uint8_t*>(r.alloc(packed.size()));r.put(a,raw.data(),raw.size());r.put(b,packed.data(),packed.size());return std::pair{a,b};
  };
  auto w=weights(37),p=projections==2?weights(1237):w;
  for(unsigned m=0;m<2;++m){
   auto &a=old[m],&b=fresh[m];a.rows=b.rows=rows;a.experts=b.experts=experts;a.count=b.count=count;a.capacity=b.capacity=4096;a.rb=old_stride;b.rb=new_stride;a.w=w.first;b.w=w.second;a.peer=p.first;b.peer=p.second;
   for(auto*z:{&a,&b}){
    z->x=static_cast<uint16_t*>(r.alloc(size_t(k)*(type==Type::IQ4_NL?count:1)*2));
    z->y=static_cast<uint16_t*>(r.alloc(size_t(rows)*count*2));z->py=static_cast<uint16_t*>(r.alloc(size_t(rows)*count*2));
    z->routes=static_cast<iq3::Route*>(r.alloc(count*sizeof(iq3::Route)));
    z->status=static_cast<uint32_t*>(r.alloc(count*4));z->peer_status=static_cast<uint32_t*>(r.alloc(count*4));
    z->active=static_cast<uint32_t*>(r.alloc(4));z->error=static_cast<uint32_t*>(r.alloc(4));z->position=static_cast<uint32_t*>(r.alloc(4));
   }
  }
 }
 void inputs(unsigned iteration,bool exact){
  std::vector<uint8_t>identity;
  for(unsigned m=0;m<2;++m){std::vector<uint16_t>x(size_t(k)*(type==Type::IQ4_NL?count:1));
   for(size_t j=0;j<x.size();++j)x[j]=iq3::bf16_bits(float(int(mix(j+iteration*104729ull+m*7919)%257)-128)/1024.f);
   if(exact&&iteration==6){x[0]=0x8000;x[8]=0x7fc3;x[16]=0xffc7;}
   if(exact&&iteration==7){x[0]=0x7f80;x[8]=0xff80;}
   std::vector<iq3::Route>routes(count);unsigned shift=m*(iteration%3==0?0:iteration%3==1?5:10);
   for(unsigned slot=0;slot<count;++slot)routes[slot]={experts==1?0u:unsigned((iteration*13+slot+shift)%experts),0,rows};
   if(exact&&iteration==2&&experts>1)routes[2].row_count=rows-1;
   if(exact&&(iteration==3||iteration==8)&&experts>1)routes[3].expert_id=experts;
   uint32_t active=exact&&iteration==4?0:1,error=exact&&(iteration==5||iteration==8)?7:0,position=37+iteration;
   auto append=[&](const void*p,size_t n){auto*b=static_cast<const uint8_t*>(p);identity.insert(identity.end(),b,b+n);};append(x.data(),x.size()*2);append(routes.data(),routes.size()*sizeof(iq3::Route));append(&active,4);append(&error,4);append(&position,4);
   for(auto*b:{&old[m],&fresh[m]}){r.put(const_cast<uint16_t*>(b->x),x.data(),x.size()*2);r.put(const_cast<iq3::Route*>(b->routes),routes.data(),routes.size()*sizeof(iq3::Route));r.put(const_cast<uint32_t*>(b->active),&active,4);r.put(b->error,&error,4);r.put(const_cast<uint32_t*>(b->position),&position,4);
    std::vector<uint8_t>poison(size_t(rows)*count*2,0xa5);r.put(b->y,poison.data(),poison.size());r.put(b->py,poison.data(),poison.size());std::vector<uint32_t>s(count,0xa5a5a5a5);r.put(b->status,s.data(),s.size()*4);r.put(b->peer_status,s.data(),s.size()*4);
   }
  }input_identity=hash(identity);
 }
 std::vector<uint8_t> capture(bool candidate,unsigned M){std::vector<uint8_t>out;
  auto append=[&](const void*p,size_t n){auto v=r.get(p,n);out.insert(out.end(),v.begin(),v.end());};
  for(unsigned m=0;m<M;++m){auto b=candidate?fresh[m]:old[m];append(b.y,size_t(rows)*count*2);append(b.py,size_t(rows)*count*2);append(b.status,count*4);append(b.peer_status,count*4);append(b.error,4);}return out;
 }
};

template<Type T,unsigned K>constexpr bool paired=T==Type::IQ2_S||T==Type::IQ3_S;
template<Type T,unsigned K>constexpr bool routed=paired<T,K>||T==Type::IQ4_NL;
template<Type T,unsigned K>std::array<float,2> control_lane(p39::Bound b,size_t source,unsigned slot,unsigned l){
 // The production P33 kernel forms the bounded byte offset in 32 bits.
 // Fixed fixture banks fit that same limit; do not weaken this control path
 // by introducing 64-bit offset multiplication in the measured lane loop.
 const unsigned offset=unsigned(source)*b.rb;
 if constexpr(paired<T,K>)return p28::expert_lane<T,K,false,true>(b.w+offset,b.peer+offset,b.x,0,K,l,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
 else if constexpr(T==Type::IQ4_NL)return {p33::down_lane<1,K>(b.w+offset,b.x+slot*K,l),0};
 else return {p33::dense_lane<T,K>(b.w+offset,b.x,0,K,l),0};
}
template<Type T,unsigned K>inline std::array<float,2> candidate_lane(p39::Bound b,size_t source,unsigned slot,unsigned l){
 if constexpr(paired<T,K>)return p48::gate_lane<T,K>(b.w+source*b.rb,b.peer+source*b.rb,b.x,0,K,l);
 else return {p48::lane<T,K>(b.w+source*b.rb,b.x+(T==Type::IQ4_NL?slot*K:0),0,K,l),0};
}
template<Type T,unsigned K,unsigned M>inline std::array<std::array<float,2>,2> candidate_values(p39::Bound a,p39::Bound b,unsigned row,unsigned slot,unsigned l){
 std::array<std::array<float,2>,2> sums{};p39::Bound bs[2]{a,b};size_t src[2]{};bool valid[2]{};
 for(unsigned m=0;m<M;++m){iq3::Route rt{0,0,a.rows};if constexpr(routed<T,K>)rt=bs[m].routes[slot];valid[m]=iq3::valid_route(rt,a.experts,a.rows,a.rows)&&row<rt.row_count;src[m]=size_t(rt.expert_id)*a.rows+rt.row_begin+row;}
 if constexpr(M==2){if(valid[0]&&valid[1]&&src[0]==src[1]){
  auto v=p48::lanes2<T,K>(a.w+src[0]*a.rb,a.x+(T==Type::IQ4_NL?slot*K:0),b.x+(T==Type::IQ4_NL?slot*K:0),0,K,l);sums[0][0]=v[0];sums[1][0]=v[1];
  if constexpr(paired<T,K>){auto p=p48::lanes2<T,K>(a.peer+src[0]*a.rb,a.x,b.x,0,K,l);sums[0][1]=p[0];sums[1][1]=p[1];}return sums;
 }}
 for(unsigned m=0;m<M;++m)if(valid[m])sums[m]=candidate_lane<T,K>(bs[m],src[m],slot,l);return sums;
}
template<Type T,unsigned K>void cpu(Job&j,bool candidate,unsigned M){
 if(!candidate){if constexpr(T==Type::IQ2_S){for(unsigned m=0;m<M;++m)p39::host_gemv<T,K,p39::Kind::expert_checks,true>(j.old[m]);return;}else if constexpr(T==Type::IQ4_NL){for(unsigned m=0;m<M;++m)p39::host_gemv<T,K,p39::Kind::down_status,true>(j.old[m]);return;}}
 for(unsigned m=0;m<M;++m){auto b=candidate?j.fresh[m]:j.old[m];
  for(unsigned s=0;s<b.count;++s){auto route=b.routes[s];bool ok=iq3::valid_route(route,b.experts,b.rows,b.rows);
   if constexpr(routed<T,K>){b.status[s]=!ok;if constexpr(paired<T,K>)b.peer_status[s]=!ok;if constexpr(T!=Type::IQ3_S)if(!ok&&*b.active&&!*b.error)*b.error=1;}
   for(unsigned row=0;row<b.rows;++row){float sums[2][32]{};bool valid=ok&&row<route.row_count;
    if(valid)for(unsigned l=0;l<32;++l){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;auto v=candidate?(M==1?candidate_values<T,K,1>(j.fresh[0],j.fresh[1],row,s,l)[m]:candidate_values<T,K,2>(j.fresh[0],j.fresh[1],row,s,l)[m]):control_lane<T,K>(b,source,s,l);sums[0][l]=v[0];sums[1][l]=v[1];}
    b.y[s*b.rows+row]=iq3::bf16_bits(valid?iq3::tree32(sums[0]):iq3::bits_float(0x7fc00000));if constexpr(paired<T,K>)b.py[s*b.rows+row]=iq3::bf16_bits(valid?iq3::tree32(sums[1]):iq3::bits_float(0x7fc00000));
   }
  }
 }
}
#ifndef OWN_RT_HOST_ONLY
template<Type T,unsigned K,unsigned M,bool Candidate>class Kernel;
template<Type T,unsigned K,unsigned M,bool Candidate>sycl::event kernel(sycl::queue&q,p39::Bound a,p39::Bound b){
 // Same one-output/SG32 ownership; M2 adds an independent accumulator per row.
 return q.submit([&](sycl::handler&h){h.parallel_for<Kernel<T,K,M,Candidate>>(sycl::nd_range<1>(size_t(a.rows)*a.count*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id(),logical=it.get_group_linear_id(),row=logical%a.rows,slot=logical/a.rows;
  p39::Bound bs[2]{a,b};iq3::Route rs[2];bool ok[2],valid[2];size_t src[2];float sums[2][2]{};
  for(unsigned m=0;m<M;++m){rs[m]={0,0,a.rows};if constexpr(routed<T,K>)rs[m]=bs[m].routes[slot];ok[m]=iq3::valid_route(rs[m],a.experts,a.rows,a.rows);valid[m]=ok[m]&&row<rs[m].row_count;src[m]=(size_t(rs[m].expert_id)*a.rows+rs[m].row_begin+row)*a.rb;}
  if constexpr(Candidate){auto v=candidate_values<T,K,M>(a,b,row,slot,l);for(unsigned m=0;m<M;++m){sums[m][0]=v[m][0];sums[m][1]=v[m][1];}}
  else for(unsigned m=0;m<M;++m)if(valid[m]){auto v=control_lane<T,K>(bs[m],src[m]/a.rb,slot,l);sums[m][0]=v[0];sums[m][1]=v[1];}
  for(unsigned m=0;m<M;++m)for(unsigned p=0;p<(paired<T,K>?2u:1u);++p)for(unsigned w=1;w<32;w*=2){float rhs=sycl::select_from_group(sg,sums[m][p],(l+w)%32);if(l%(2*w)==0)sums[m][p]=sums[m][p]+rhs;}
  if(l==0)for(unsigned m=0;m<M;++m){auto z=bs[m];z.y[logical]=iq3::bf16_bits(valid[m]?sums[m][0]:iq3::bits_float(0x7fc00000));if constexpr(paired<T,K>)z.py[logical]=iq3::bf16_bits(valid[m]?sums[m][1]:iq3::bits_float(0x7fc00000));if constexpr(routed<T,K>)if(row==0){z.status[slot]=!ok[m];if constexpr(paired<T,K>)z.peer_status[slot]=!ok[m];if constexpr(T!=Type::IQ3_S)if(!ok[m]&&*z.active)p39::sticky_fail(z);}}
 });});
}
template<Type T,unsigned K>std::vector<Timing> gpu(Job&j,bool candidate,unsigned M){
 auto&q=*j.r.queue;std::vector<sycl::event>events;
 if(candidate){events.push_back(M==1?kernel<T,K,1,true>(q,j.fresh[0],j.fresh[1]):kernel<T,K,2,true>(q,j.fresh[0],j.fresh[1]));}
 else for(unsigned m=0;m<M;++m){
  // Actual current fused production kernels, not the stale dispatch-string body.
  if constexpr(T==Type::IQ2_S)events.push_back(p39::gemv<T,K,p39::Kind::expert_checks,true>(q,j.old[m]).front());
  else if constexpr(T==Type::IQ4_NL)events.push_back(p39::gemv<T,K,p39::Kind::down_status,true>(q,j.old[m]).front());
  else events.push_back(kernel<T,K,1,false>(q,j.old[m],j.old[m]));
 }
 j.r.drain();std::vector<Timing>out;for(auto&e:events){auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>(),b=e.get_profiling_info<sycl::info::event_profiling::command_end>();need(a&&b>a&&b-a<4000000000ull,"invalid GPU event");out.push_back({a,b});}return out;
}
#endif

static std::vector<std::string> output_hashes;
template<Type T,unsigned K>void run_case(Runtime&r,const std::string&name,unsigned rows,unsigned experts,unsigned projections,bool timing,std::ofstream&cmp,std::ofstream&tim){
#ifdef OWN_RT_HOST_ONLY
 rows=5;experts=experts==1?1:20;
#endif
 Job j(r,T,K,rows,experts,projections);
 for(unsigned M:{1u,2u})for(unsigned iteration=0;iteration<(timing?28u:9u);++iteration){need(!stopping,"cooperative stop");j.inputs(iteration,!timing);std::array<std::vector<Timing>,2>measured;
  for(unsigned arm=0;arm<2;++arm){bool candidate=bool(arm^(iteration%2));
#ifdef OWN_RT_HOST_ONLY
   cpu<T,K>(j,candidate,M);
#else
   measured[candidate]=gpu<T,K>(j,candidate,M);
#endif
  }
  auto a=j.capture(false,M),b=j.capture(true,M);need(a==b,"raw output/status byte mismatch");auto digest=hash(a);output_hashes.push_back(digest);
  cmp<<"{\"class\":\""<<name<<"\",\"M\":"<<M<<",\"iteration\":"<<iteration<<",\"bytes\":"<<a.size()<<",\"sha256\":\""<<digest<<"\",\"input_sha256\":\""<<j.input_identity<<"\",\"equal\":true}\n";cmp.flush();
  if(timing)for(unsigned arm=0;arm<2;++arm){uint64_t ns=0;for(auto&e:measured[arm])ns+=e.end-e.start;tim<<"{\"class\":\""<<name<<"\",\"M\":"<<M<<",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<4?"true":"false")<<",\"candidate\":"<<(arm?"true":"false")<<",\"gpu_ns\":"<<ns<<",\"events\":[";for(size_t e=0;e<measured[arm].size();++e){auto t=measured[arm][e];tim<<(e?",":"")<<"{\"start_ns\":"<<t.start<<",\"end_ns\":"<<t.end<<"}";}tim<<"]}\n";tim.flush();}
 }
 r.release();
}
int main(int argc,char**argv){std::unique_ptr<Runtime>rt;fs::path output;bool timing=false,cpu_only=false,authorized=false;int card=-1;try{
 for(int i=1;i<argc;++i){std::string a=argv[i];auto v=[&]{need(++i<argc,"missing option value");return std::string(argv[i]);};if(a=="--output")output=v();else if(a=="--mode"){auto m=v();need(m=="exact"||m=="timing","mode");timing=m=="timing";}else if(a=="--card")card=std::stoi(v());else if(a=="--cpu-test")cpu_only=true;else if(a=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown argument");}
 need(!output.empty()&&!fs::exists(output),"new output required");
#ifdef OWN_RT_HOST_ONLY
 need(cpu_only&&!authorized&&card==-1&&!timing,"CPU mock only");
#else
 need(!cpu_only&&authorized&&card==0,"physical card0 coordinator only");
#endif
 fs::create_directories(output);std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 rt=std::make_unique<Runtime>();std::ofstream cmp(output/"comparisons.jsonl"),tim(output/"iterations.jsonl");
 run_case<Type::IQ2_S,2560>(*rt,"expsgate.iq2",640,512,2,timing,cmp,tim);
 run_case<Type::IQ4_NL,640>(*rt,"expsdown",2560,512,1,timing,cmp,tim);
 run_case<Type::Q6_K,2560>(*rt,"gdn.qkv.q6",10240,1,1,timing,cmp,tim);
 run_case<Type::Q6_K,2560>(*rt,"gdn.z.q6",6144,1,1,timing,cmp,tim);
 run_case<Type::IQ3_S,2560>(*rt,"expsgate.iq3",640,512,2,timing,cmp,tim);
 run_case<Type::Q8_0,2560>(*rt,"gdn.qkv.q8",10240,1,1,timing,cmp,tim);
 run_case<Type::Q8_0,2560>(*rt,"gdn.z.q8",6144,1,1,timing,cmp,tim);
 rt->close();std::string joined;for(auto&h:output_hashes)joined+=h;
 std::ofstream rec(output/"receipt.json");rec<<"{\"schema\":\"ownrt.packet48.native.v1\",\"passed\":true,\"device_executed\":"<<(cpu_only?"false":"true")<<",\"mode\":\""<<(timing?"timing":"exact")<<"\",\"safe_teardown\":true,\"checks\":"<<output_hashes.size()<<",\"exact_output_identity\":\""<<hash(joined.data(),joined.size())<<"\",\"device\":\""<<rt->identity<<"\"}\n";need(bool(rec),"receipt write");std::cout<<"passed "<<output_hashes.size()<<" byte comparisons\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';if(rt)try{rt->close();}catch(...){std::cerr<<"uncertain device drain; owner retained for coordinator\n";for(;;)std::this_thread::sleep_for(std::chrono::seconds(30));}return 1;}
}
