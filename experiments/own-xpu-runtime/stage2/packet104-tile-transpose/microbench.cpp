// Packet100 real-route harness extended to packet104's copied operation bodies.
#include "p104iq2.hpp"
#include "p104iq2hc.hpp"
#include "p104_draft.hpp"
#include "p104_hc.hpp"
#include "p59_draft.hpp"
#include "p73_hc.hpp"
#include <csignal>
#include <atomic>
#include <fstream>
#include <iostream>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
struct Buffers{
 sycl::queue&q;std::vector<void*>values;
 ~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto p:values)sycl::free(p,q);}
 template<class T>T*alloc(size_t count){auto*p=sycl::malloc_device<T>(count,q);if(!p)throw std::bad_alloc();values.push_back(p);return p;}
};
template<bool HC>struct Target {
 static constexpr unsigned rows=640,K=2560,count=10,experts=512,wg=64;
 static constexpr size_t rb=HC?840:820;static constexpr bool paired=true,routed=true;
 using Prod=std::conditional_t<HC,p90exp::Kernel<iq3::Type::IQ2_S,K,64,false,true>,p65::Kernel<iq3::Type::IQ2_S,K,64,false,true>>;
 using Tile=std::conditional_t<HC,p104iq2hc::Kernel<iq3::Type::IQ2_S,K,64,false,true>,p104iq2::Kernel<iq3::Type::IQ2_S,K,64,false,true>>;
 static const char*name(){return HC?"target-gate-halfcache-tile16":"target-gate-tile16";}
 static auto transpose(const uint8_t*p,size_t n){return p104::iq2<HC>(p,n);}
 template<class Next>static void initialize(std::vector<uint8_t>&v,Next next){
  for(auto&b:v)b=next()>>24;
  for(size_t r=0;r<v.size()/rb;++r)for(unsigned k=0;k<10;++k){uint16_t h=0x2400+next()%1024;
   if constexpr(HC){float f=iq3::half(h);std::memcpy(v.data()+r*rb+800+4*k,&f,4);}else std::memcpy(v.data()+r*rb+800+2*k,&h,2);}
 }
 template<bool Tiled>static float raw(const uint8_t*w,const uint16_t*x,size_t row,unsigned lane){
  if constexpr(Tiled){using C=Tile;return p49dvirtual::local_tree<8>(C::chains(w,row,x,lane));}
  else return p49dvirtual::local_tree<8>(Prod::chains(w+row*rb,x,lane));
 }
 static constexpr unsigned lanes=4;
 static sycl::event launch(sycl::queue&q,bool tile,const std::array<void*,19>&p){return tile?Tile{}.submit(q,p,{}):Prod{}.submit(q,p,{});}
};
template<unsigned Columns,bool Int8,bool Pair,unsigned V>struct Draft {
 static constexpr unsigned K=Columns,rows=K==2560?640:2560,count=Int8?10:1,experts=Int8?512:1,wg=256,lanes=32/V;
 static constexpr size_t rb=Int8?K+K/16*4:K*2;static constexpr bool paired=Pair,routed=Int8;
 using Prod=p59::Dense<K,Int8,Pair,V,1>;using Tile=p104draft::Dense<K,Int8,Pair,V,1>;
 static const char*name(){if constexpr(Int8)return Pair?"draft-gate-tile16":"draft-down-tile16";else return K==2560?"shared-gate-up-tile16":"shared-down-tile16";}
 static auto transpose(const uint8_t*p,size_t n){return p104::draft<K,Int8>(p,n);}
 template<class Next>static void initialize(std::vector<uint8_t>&v,Next next){
  for(size_t r=0;r<v.size()/rb;++r){auto*p=v.data()+r*rb;
   if constexpr(Int8){for(unsigned k=0;k<K;++k)p[k]=next()>>24;for(unsigned k=0;k<K/16;++k){float f=float(1+next()%63)/128.f;std::memcpy(p+K+4*k,&f,4);}}
   else for(unsigned k=0;k<K;++k){uint16_t v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);std::memcpy(p+2*k,&v,2);}
  }
 }
 template<bool Tiled>static float raw(const uint8_t*w,const uint16_t*x,size_t row,unsigned lane){
  if constexpr(Tiled)return Tile::chain(w,x,lane,0,row);else return Prod::chain(w+row*rb,x,lane,0);
 }
 static sycl::event launch(sycl::queue&q,bool tile,const std::array<void*,19>&p){
  p59::Linear a;a.rows=rows;a.columns=K;a.batch=count;a.experts=experts;a.int8=Int8;a.paired=Pair;
  a.routes=Int8?ownrt::Allocation{1}:ownrt::Allocation{};
  a.tail=(Pair||(!Int8&&K==2560))?p59::product:p59::none;
  if(tile){Tile op;op.a.rows=rows;op.a.columns=K;op.a.batch=count;op.a.experts=experts;op.a.int8=Int8;op.a.paired=Pair;op.a.routes=a.routes;op.a.tail=decltype(op.a.tail)(a.tail);return op.submit(q,std::span<void*const>(p.data(),11),{});}
  Prod op;op.a=a;return op.submit(q,std::span<void*const>(p.data(),11),{});
 }
};
// HC's actual fused gate+mix operation, including four streams and status guard.
struct HC {
 static constexpr unsigned rows=10240,K=320,count=1,experts=1,wg=256,lanes=32;
 static constexpr size_t rb=380;static constexpr bool paired=false,routed=false;
 static const char*name(){return "hc-gate-tile16";}
 static auto transpose(const uint8_t*p,size_t n){return p104::hc(p,n);}
 template<class Next>static void initialize(std::vector<uint8_t>&v,Next next){
  for(auto&b:v)b=next()>>24;
  for(size_t r=0;r<v.size()/rb;++r)for(unsigned k=0;k<10;++k){float f=float(1+next()%63)/128.f;std::memcpy(v.data()+r*rb+320+4*k,&f,4);}
 }
 template<bool Tiled>static float raw(const uint8_t*w,const uint16_t*x,size_t row,unsigned lane){
  if constexpr(Tiled)return p104hc::chains(w,x,lane,row-row%2)[row%2];else return p73hc::chains(w+(row-row%2)*rb,x,lane)[row%2];
 }
 static sycl::event launch(sycl::queue&q,bool tile,const std::array<void*,19>&p){
  p60::Bound b{};b.gate_w=(uint8_t*)p[0];b.act=(uint16_t*)p[2];b.gate=(uint16_t*)p[3];b.mix=(uint16_t*)p[8];b.norm=(uint16_t*)p[9];b.error=(uint32_t*)p[16];b.active=(uint32_t*)p[17];b.position=(uint32_t*)p[18];
  return tile?p104hc::device(q,b,{}):p73hc::device(q,b,{});
 }
};
template<class Op,bool Tiled>sycl::event raw_kernel(sycl::queue&q,const uint8_t*w,const uint8_t*peer,const uint16_t*x,const iq3::Route*routes,float*y){
 constexpr unsigned n=Op::rows*Op::count,lanes=Op::lanes;
 return q.submit([&](sycl::handler&h){h.parallel_for(sycl::nd_range<1>((size_t(n)*lanes+255)/256*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  unsigned i=it.get_global_linear_id()/lanes,lane=it.get_local_linear_id()%lanes;if(i>=n)return;
  unsigned slot=i/Op::rows,row=i%Op::rows;size_t source=row;
  if constexpr(Op::routed)source=size_t(routes[slot].expert_id)*Op::rows+row;
  const uint16_t*input=x+(Op::paired?0:size_t(slot)*Op::K);
  float a=Op::template raw<Tiled>(w,input,source,lane),b=0;if constexpr(Op::paired)b=Op::template raw<Tiled>(peer,input,source,lane);
  auto sg=it.get_sub_group();unsigned base=sg.get_local_linear_id()-lane;
  for(unsigned d=1;d<lanes;d*=2){float rhs=sycl::select_from_group(sg,a,base+(lane+d)%lanes),pr=sycl::select_from_group(sg,b,base+(lane+d)%lanes);if(lane%(2*d)==0){a+=rhs;b+=pr;}}
  if(!lane){y[i]=a;if constexpr(Op::paired)y[n+i]=b;}
 });});
}
template<class Op>void benchmark(sycl::queue&q,const std::vector<iq3::Route>&captured){
 constexpr unsigned n=Op::rows*Op::count;
 constexpr size_t bytes=size_t(Op::experts)*Op::rows*Op::rb,scrub_words=size_t(128)*1024*1024;
 Buffers b{q,{}};auto*w=b.alloc<uint8_t>(bytes);auto*t=b.alloc<uint8_t>(bytes);
 auto*peer=Op::paired?b.alloc<uint8_t>(bytes):w;auto*pt=Op::paired?b.alloc<uint8_t>(bytes):t;
 auto*x=b.alloc<uint16_t>(Op::K*Op::count);auto*routes=b.alloc<iq3::Route>(10);
 // Contiguous outputs allow checking guards, both streams, fused tails and status.
 auto*out=b.alloc<uint16_t>(n*3);auto*other=b.alloc<uint16_t>(std::max(n,unsigned(10240)));
 auto*status=b.alloc<uint32_t>(20);auto*control=b.alloc<uint32_t>(3);
 auto*f=b.alloc<float>(n*(Op::paired?2:1));auto*scrub=b.alloc<uint32_t>(scrub_words);
 uint32_t seed=104;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
 for(unsigned stream=0;stream<(Op::paired?2u:1u);++stream)for(unsigned first=0;first<Op::experts*Op::rows;first+=256){guard();unsigned nr=std::min(256u,Op::experts*Op::rows-first);std::vector<uint8_t>raw(size_t(nr)*Op::rb);Op::initialize(raw,next);auto trans=Op::transpose(raw.data(),nr);
  q.memcpy((stream?peer:w)+size_t(first)*Op::rb,raw.data(),raw.size()).wait_and_throw();q.memcpy((stream?pt:t)+size_t(first)*Op::rb,trans.data(),trans.size()).wait_and_throw();}
 std::vector<uint16_t>ho(std::max(n,unsigned(10240)));for(auto&v:ho)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);q.memcpy(other,ho.data(),ho.size()*2).wait_and_throw();
 uint32_t controls[3]={0,1,0};q.memcpy(control,controls,12).wait_and_throw();
 std::array<void*,19>pp{};pp[0]=w;pp[1]=peer;pp[2]=x;pp[3]=out;pp[4]=out+n;pp[5]=routes;pp[6]=status;pp[7]=status+10;pp[8]=out+2*n;pp[9]=other;pp[10]=other;pp[16]=control;pp[17]=control+1;pp[18]=control+2;
 auto tp=pp;tp[0]=t;tp[1]=pt;
 auto launch=[&](bool tile){return Op::launch(q,tile,tile?tp:pp);};
 auto cold=[&]{q.parallel_for(sycl::range<1>(scrub_words),[=](sycl::id<1>id){scrub[id]=uint32_t(id[0]);}).wait_and_throw();};
 unsigned cases=Op::routed?captured.size()/10:8;
 std::vector<uint16_t>hx(Op::K*Op::count),ey(n*3),ay(n*3);std::vector<float>ef(n*(Op::paired?2:1)),af(ef.size());std::array<uint32_t,20>es{},as{};
 for(unsigned ri=0;ri<cases;++ri){guard();std::array<iq3::Route,10>rs{};
  for(unsigned s=0;s<10;++s)rs[s]={Op::routed?captured[ri*10+s].expert_id:0,0,Op::rows};q.memcpy(routes,rs.data(),120).wait_and_throw();
  for(auto&v:hx)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);q.memcpy(x,hx.data(),hx.size()*2).wait_and_throw();
  for(unsigned arm=0;arm<2;++arm){q.memset(out,0x5a,n*6).wait_and_throw();q.memset(status,0x5a,80).wait_and_throw();
   if(arm)raw_kernel<Op,true>(q,t,pt,x,routes,f).wait_and_throw();else raw_kernel<Op,false>(q,w,peer,x,routes,f).wait_and_throw();launch(arm).wait_and_throw();
   q.memcpy(arm?af.data():ef.data(),f,ef.size()*4).wait_and_throw();q.memcpy(arm?ay.data():ey.data(),out,n*6).wait_and_throw();q.memcpy(arm?as.data():es.data(),status,80).wait_and_throw();}
  q.memcpy(controls,control,12).wait_and_throw();
  if(std::memcmp(ef.data(),af.data(),ef.size()*4)||ey!=ay||es!=as||controls[0]||controls[1]!=1||controls[2])throw std::runtime_error(std::string(Op::name())+" FP32/BF16/epilogue/status mismatch");
  auto shape=[&]{std::cout<<",\"rows\":"<<Op::rows<<",\"columns\":"<<Op::K<<",\"count\":"<<Op::count<<",\"experts\":"<<Op::experts;};
  std::cout<<"{\"kind\":\"correctness\",\"view\":\""<<Op::name()<<"\",\"route\":"<<ri<<",\"fp32_exact\":true,\"bf16_exact\":true,\"status_exact\":true";shape();std::cout<<"}\n";
  for(unsigned rep=0;rep<40;++rep)for(unsigned pos=0;pos<2;++pos){guard();bool arm=bool(pos^(rep&1));cold();auto e=launch(arm);e.wait_and_throw();auto ns=e.template get_profiling_info<sycl::info::event_profiling::command_end>()-e.template get_profiling_info<sycl::info::event_profiling::command_start>();
   std::cout<<"{\"kind\":\"sample\",\"pair\":\""<<Op::name()<<"\",\"view\":\""<<(arm?Op::name():"production")<<"\",\"route\":"<<ri<<",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"event_ns\":"<<ns;shape();std::cout<<",\"wg\":"<<Op::wg<<",\"sg\":32,\"scrub_bytes\":536870912,\"diagnostic_only\":true}\n";}
  std::cout<<std::flush;
 }
 q.wait_and_throw();guard();
}
int main(int argc,char**argv){try{
 if(argc!=3||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("coordinator admission and route payload required");
 std::ifstream in(argv[2],std::ios::binary);std::vector<uint8_t>raw((std::istreambuf_iterator<char>(in)),{});
 if(!in||raw.size()!=384*120)throw std::runtime_error("complete packet100b real route payload required");
 std::vector<iq3::Route>rs(raw.size()/12);std::memcpy(rs.data(),raw.data(),raw.size());
 for(auto r:rs)if(r.expert_id>=512||r.row_begin||r.row_count!=2560)throw std::runtime_error("invalid captured routes");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 {sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});
  benchmark<Target<false>>(q,rs);benchmark<Target<true>>(q,rs);
  benchmark<Draft<2560,true,true,8>>(q,rs);benchmark<Draft<640,true,false,16>>(q,rs);
  benchmark<Draft<2560,false,false,1>>(q,rs);benchmark<Draft<640,false,false,4>>(q,rs);benchmark<HC>(q,rs);
  q.wait_and_throw();guard();}
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"candidate_count\":7,\"route_count\":384,\"diagnostic_only\":true}\n"<<std::flush;return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
