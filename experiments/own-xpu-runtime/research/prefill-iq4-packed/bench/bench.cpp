// CPU-device bitwise test of the expert-grouped prefill tiles (prefill_experts.hpp) against host replicas of the existing
// routed kernels' per-lane sequences (iq3block BlockRows, gsqn PackedRows incl. Q2_0, kopt MultiplyBlockRows).
#include "group_iq4_packed.hpp"
#include "harness.hpp"
#include <fstream>
#include <chrono>
#include "stage2/packet2/kernels/math.hpp"
#include "gsq-rco-iq3s/integration/build/private/additive/device_formats.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_experts.hpp"
#include <bit>
#include <cstdio>
#include <cstring>
#include <functional>
#include <random>
#include <vector>
using namespace iq3;
// verbatim copy of iq3block::block_element_words
inline float block_element_words(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const uint32_t index=(uint32_t(reinterpret_cast<const uint16_t*>(b+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
 const auto mag=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
// policies as in prefill_experts_policies.hpp
struct Iq3Words {static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){
 const uint8_t* packed=row+step*98u;const float d=iq3::half(iq3::u16(packed));
 for(unsigned g=0;g<8;++g)if(g<gv)v[g]=block_element_words(packed,d,g,lane);}};
template<unsigned T> struct Elem {static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){
 constexpr uint32_t elements=T==42?64:256,bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 for(unsigned g=0;g<8;++g)if(g<gv){const uint32_t k=step*256u+g*32u+lane;v[g]=gsq::element_unchecked(T,row+(k/elements)*bytes,k%elements);}}};
template<iq3::Type T> struct Kopt {static void decode8(const uint8_t* row,uint32_t k,float (&v)[8]){iq3::kopt::decode8<T>(row,k,v);}};
static float tree(float* s){for(unsigned w=1;w<32;w*=2)for(unsigned i=0;i<32;i+=2*w)s[i]=s[i]+s[i+w];return s[0];}
static uint16_t rhalf(std::mt19937& g){std::uniform_real_distribution<float> u(0.0005f,0.05f);sycl::half h=sycl::half(u(g));uint16_t b;std::memcpy(&b,&h,2);return b;}
// host lane references -------------------------------------------------------------------------------------------------
float ref_iq3(const uint8_t* w,const float* x,uint32_t K,unsigned lane){float acc=0;
 for(uint32_t block=0;block<K/256;++block){const auto*packed=w+block*98u;const float d=iq3::half(iq3::u16(packed));
  for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;const float weight=block_element_words(packed,d,group,lane);const float product=weight*x[k];acc=acc+product;}}
 return acc;}
template<unsigned T> float ref_elem(const uint8_t* w,const float* x,uint32_t K,unsigned lane){float acc=0;
 constexpr uint32_t elements=T==42?64:256,bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 if constexpr(T==42){
  for(uint32_t block=0;block<K/64u;++block){const float d=iq3::half(iq3::u16(w+block*18u));
   for(unsigned h=0;h<2;++h){const uint32_t e=lane+32u*h,k=block*64u+e;const float input=x[k];
    const unsigned code=(w[block*18u+2u+e/4u]>>(2*(e%4u)))&3;const float weight=float(int(code)-1)*d;const float product=weight*input;acc=acc+product;}}
 } else for(uint32_t k=lane;k<K;k+=32){const float input=x[k];const float weight=gsq::element_unchecked(T,w+(k/elements)*bytes,k%elements);const float product=weight*input;acc=acc+product;}
 return acc;}
template<iq3::Type T> float ref_kopt(const uint8_t* w,const float* x,uint32_t K,unsigned lane){float acc=0;uint32_t k=lane*8u;
 for(;k+8u<=K;k+=256u){float input[8];for(unsigned j=0;j<8;++j)input[j]=x[k+j];float values[8];iq3::kopt::decode8<T>(w,k,values);
  for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc=acc+product;}}
 return acc;}
// ---------------------------------------------------------------------------------------------------------------------
struct Case{const char* name;uint32_t rows,k,rb,experts;std::function<void(std::mt19937&,uint8_t*)> fill_row;std::function<float(const uint8_t*,const float*,uint32_t,unsigned)> ref;};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF>
int run(sycl::queue& q,const Case& c,uint32_t n,const uint8_t* w,const float* x,const Route* routes,const std::vector<float>& want,const std::vector<uint32_t>& wst){
 float* y=sycl::malloc_shared<float>(size_t(n)*c.rows,q);for(size_t i=0;i<size_t(n)*c.rows;++i)y[i]=-12345.f;
 uint32_t* st=sycl::malloc_shared<uint32_t>(n,q);uint32_t* order=sycl::malloc_shared<uint32_t>(n,q);uint32_t* tiles=sycl::malloc_shared<uint32_t>(n*5,q);uint32_t* cnt=sycl::malloc_shared<uint32_t>(16,q);
 for(uint32_t i=0;i<n;++i)st[i]=77;
 xgroup::Bucket b{routes,st,order,tiles,cnt,n,c.experts,c.rows,c.rows,T,{}};
 q.submit([&](sycl::handler& h){auto bb=b;bb.keys=sycl::local_accessor<uint32_t,1>(sycl::range<1>(n),h);h.parallel_for(sycl::nd_range<1>(xgroup::bucket_items,xgroup::bucket_items),bb);}).wait();
 auto p=xgroup::prepare<F,RW,T,S,GRF>(w,x,y,order,tiles,cnt,c.rows,c.k,c.rb,n,c.experts);auto kernel=p.kernel;
 auto reference=[&](){return q.submit([&](sycl::handler& h){h.parallel_for(p.range,kernel);});};
 auto candidate=[&](){return packed_group::launch(q,w,x,y,order,tiles,cnt,c.rows,c.k,c.rb,n,c.experts);};
 std::vector<float> production_want;
 if(c.rows==2560){reference().wait_and_throw();production_want.assign(y,y+size_t(n)*c.rows);}
 candidate().wait_and_throw();
 size_t bad=0;for(size_t i=0;i<size_t(n)*c.rows;++i){uint32_t a,bw;std::memcpy(&a,&y[i],4);std::memcpy(&bw,c.rows==2560?&production_want[i]:&want[i],4);if(a!=bw){if(bad<3)printf("   mismatch %s i=%zu got %08x want %08x\n",c.name,i,a,bw);++bad;}}
 for(uint32_t i=0;i<n;++i)if(st[i]!=wst[i]){if(bad<5)printf("   status mismatch slot %u\n",i);++bad;}
 printf("  %-7s slots %3u tiles %3u cfg RW%u T%u S%u GRF%u : %s\n",c.name,n,*cnt,RW,T,S,GRF,bad?"FAIL":"ok");
 if(!bad&&c.rows==2560){Bench b(q,y,size_t(n)*c.rows);b.add("incumbent_xgroup_1x4",reference);b.add("packed_logical4_T4",candidate);b.run(6,8);}
 sycl::free(y,q);sycl::free(st,q);sycl::free(order,q);sycl::free(tiles,q);sycl::free(cnt,q);return bad?1:0;}
template<class F> int all(sycl::queue& q,const Case& c,uint32_t n,const uint8_t* w,const float* x,const Route* r,const std::vector<float>& want,const std::vector<uint32_t>& st){
 int f=run<F,1,4,4,128>(q,c,n,w,x,r,want,st);
 return f;}
int main(){
 auto dev=sycl::device(sycl::gpu_selector_v);printf("device: %s\n",dev.get_info<sycl::info::device::name>().c_str());
 sycl::queue q(dev,{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()});
 std::mt19937 g(4321);std::uniform_int_distribution<int> byte(0,255);
 auto fill_random=[&](uint8_t* p,size_t n){for(size_t i=0;i<n;++i)p[i]=uint8_t(byte(g));};
 int fails=0;
 auto go=[&](Case c,auto fmt,uint32_t tokens,int mode){
  using F=decltype(fmt);const uint32_t n=tokens*10;
  uint8_t* w=sycl::malloc_shared<uint8_t>(size_t(c.experts)*c.rows*c.rb+64,q);float* x=sycl::malloc_shared<float>(size_t(n)*c.k,q);Route* routes=sycl::malloc_shared<Route>(n,q);
  for(uint32_t r=0;r<c.experts*c.rows;++r)c.fill_row(g,w+size_t(r)*c.rb);
  std::uniform_real_distribution<float> u(-1.f,1.f);std::uniform_int_distribution<int> ex(-6,6);
  for(size_t i=0;i<size_t(n)*c.k;++i)x[i]=std::ldexp(u(g),ex(g));
  std::uniform_int_distribution<int> pick(0,int(c.experts)-1),rare(0,99);
  for(uint32_t s=0;s<n;++s){Route r{uint32_t(pick(g)),0,c.rows};
   if(mode==1){int z=rare(g);if(z<4)r.expert_id=c.experts+uint32_t(z);else if(z<8){r.row_begin=3;r.row_count=c.rows-7;}else if(z<10){r.row_begin=0;r.row_count=c.rows+1;}}
   routes[s]=r;}
  std::vector<float> want(size_t(n)*c.rows);std::vector<uint32_t> st(n);
  if(c.rows==2560){std::ifstream f("routes256.bin",std::ios::binary);f.read(reinterpret_cast<char*>(routes),n*sizeof(Route));if(!f)throw std::runtime_error("route census read");}
  if(c.rows!=2560)for(uint32_t s=0;s<n;++s){const Route r=routes[s];const bool v=valid_route(r,c.experts,c.rows,c.rows);st[s]=v?0:1;
   for(uint32_t row=0;row<c.rows;++row){float out=bits_float(0x7fc00000);
    if(v&&row<r.row_count){float lanes[32];const uint8_t* wr=w+(size_t(r.expert_id)*c.rows+r.row_begin+row)*c.rb;for(unsigned l=0;l<32;++l)lanes[l]=c.ref(wr,x+size_t(s)*c.k,c.k,l);out=tree(lanes);}
    want[size_t(s)*c.rows+row]=out;}}
  fails+=all<F>(q,c,n,w,x,routes,want,st);sycl::free(w,q);sycl::free(x,q);sycl::free(routes,q);
 };
 auto halfblocks=[&](uint32_t bytes,uint32_t blocks,uint32_t doff){return [=,&fill_random](std::mt19937& gg,uint8_t* r){fill_random(r,size_t(bytes)*blocks);for(uint32_t b=0;b<blocks;++b){uint16_t d=rhalf(gg);std::memcpy(r+b*bytes+doff,&d,2);}};};
 for(int mode:{0,1})for(uint32_t tokens:{1u,7u,32u})for(uint32_t k:{256u,640u,768u}){
  Case c{"IQ4_NLd",41,k,k/32*18,9,halfblocks(18,k/32,0),ref_kopt<Type::IQ4_NL>};go(c,xgroup::C8<Kopt<Type::IQ4_NL>>{},tokens,mode);
  if(fails)return 1;
 }
 {Case c{"IQ4_prod",2560,640,360,512,halfblocks(18,20,0),ref_kopt<Type::IQ4_NL>};go(c,xgroup::C8<Kopt<Type::IQ4_NL>>{},256,0);}
 printf("TOTAL FAILS %d\n",fails);return fails?1:0;
}
