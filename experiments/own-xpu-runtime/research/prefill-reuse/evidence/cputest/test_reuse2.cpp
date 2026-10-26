// CPU-device bitwise test of reuse2 tile kernels against host replicas of the original per-lane sequences.
#include <sycl/sycl.hpp>
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_reuse2.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include <functional>
using namespace iq3;
// verbatim copy of denseblock::block_element (block.hpp)
template<unsigned T> inline float block_element(const uint8_t*b,float d,float dmin,unsigned group,unsigned lane){
 static_assert(T==12||T==13||T==23);
 if constexpr(T==12||T==13){
  const auto*s=b+4;
  const unsigned scale=group<4?s[group]&63:(s[group+4]&15)|((s[group-4]>>6)<<4);
  const unsigned minimum=group<4?s[group+4]&63:(s[group+4]>>4)|((s[group]>>6)<<4);
  constexpr unsigned low_offset=T==12?16:48;
  unsigned code=(b[low_offset+(group/2)*32+lane]>>(4*(group%2)))&15;
  if constexpr(T==13)code|=((b[16+lane]>>group)&1)<<4;
  const float factor=d*float(scale);
  const float offset=dmin*float(minimum);
  const float product=factor*float(code);return product-offset;
 }else{
  constexpr int levels[]{-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
  const unsigned scale=((b[4+group/2]>>(4*(group%2)))&15)|(((iq3::u16(b+2)>>(2*group))&3)<<4);
  const unsigned code=(b[8+group*16+lane%16]>>(4*(lane/16)))&15;
  const float factor=d*float(int(scale)-32);
  return factor*float(levels[code]);
 }
}
struct BE{template<unsigned T> static float element(const uint8_t*b,float d,float dmin,unsigned g,unsigned l){return block_element<T>(b,d,dmin,g,l);}};
struct Q6D{static void decode8(const uint8_t* r,uint32_t k,float (&v)[8]){iq3::kopt::decode8<Type::Q6_K>(r,k,v);}};
struct Q8D{static void decode8(const uint8_t* r,uint32_t k,float (&v)[8]){iq3::kopt::decode8<Type::Q8_0>(r,k,v);}};
static float tree(float* s){for(unsigned w=1;w<32;w*=2)for(unsigned i=0;i<32;i+=2*w)s[i]=s[i]+s[i+w];return s[0];}
static uint16_t rhalf(std::mt19937& g){std::uniform_real_distribution<float> u(0.0005f,0.05f);float f=u(g);sycl::half h=sycl::half(f);uint16_t b;std::memcpy(&b,&h,2);return b;}
// host references -----------------------------------------------------------------------------------------------------
template<unsigned T> float ref_block(const uint8_t* w,const float* x,uint32_t k,unsigned lane){
 constexpr size_t bytes=T==12?144:T==13?176:136;float sum=0;
 for(size_t block=0;block<k/256;++block){const auto*packed=w+block*bytes;const float d=iq3::half(iq3::u16(packed));
  float dmin=0;if constexpr(T==12||T==13)dmin=iq3::half(iq3::u16(packed+2));
  for(unsigned group=0;group<8;++group){const size_t kk=block*256+group*32+lane;const float weight=block_element<T>(packed,d,dmin,group,lane);const float product=weight*x[kk];sum=sum+product;}}
 return sum;
}
template<unsigned G> float ref_expanded(const uint8_t* w,const float* x,uint32_t K,unsigned lane){
 float sum=0;
 for(unsigned tile=lane*8;tile<K;tile+=256){const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/G)));
  for(unsigned j=0;j<8;++j)if(tile+j<K){float value=scale*float(iq3::signed8(w[tile+j]));float input=x[tile+j];float product=value*input;sum=sum+product;}}
 return sum;
}
float ref_bf16(const uint8_t* w,const float* x,uint32_t K,unsigned lane){
 float acc=0;const uint16_t* r=reinterpret_cast<const uint16_t*>(w);uint32_t base=lane*8u;
 for(;base+8u<=K;base+=256u){float values[8],wide[8];for(unsigned j=0;j<8;++j)wide[j]=x[base+j];for(unsigned j=0;j<8;++j)values[j]=bits_float(uint32_t(r[base+j])<<16);
  for(unsigned j=0;j<8;++j){float product=values[j]*wide[j];acc=acc+product;}}
 return acc;
}
template<Type TT> float ref_raw(const uint8_t* w,const float* x,uint32_t K,unsigned lane){
 float acc=0;
 for(size_t k=size_t(lane)*8;k<K;k+=256){float values[8];iq3::kopt::decode8<TT>(w,uint32_t(k),values);
  for(unsigned j=0;j<8&&k+j<K;++j){float input=x[k+j];float product=values[j]*input;acc=acc+product;}}
 return acc;
}
// ---------------------------------------------------------------------------------------------------------------------
struct Case{const char* name;uint32_t rows,k,rb;std::function<void(std::mt19937&,uint8_t*)> fill_row;std::function<float(const uint8_t*,const float*,uint32_t,unsigned)> ref;};
template<class F,unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O=0>
int run(sycl::queue& q,const Case& c,uint32_t tokens,const uint8_t* w,const float* x,const std::vector<float>& want){
 float* y=sycl::malloc_shared<float>(size_t(tokens)*c.rows,q);for(size_t i=0;i<size_t(tokens)*c.rows;++i)y[i]=-12345.f;
 auto p=reuse2::prepare<F,RW,T,S,GRF,O>(w,x,y,c.rows,c.k,tokens,c.rb);auto kernel=p.kernel;
 q.submit([&](sycl::handler& h){h.parallel_for(p.range,kernel);}).wait();
 size_t bad=0;for(size_t i=0;i<size_t(tokens)*c.rows;++i){uint32_t a,b;std::memcpy(&a,&y[i],4);std::memcpy(&b,&want[i],4);if(a!=b){if(bad<3)printf("   mismatch %s cfg %ux%u i=%zu got %08x want %08x\n",c.name,RW,T,i,a,b);++bad;}}
 sycl::free(y,q);printf("  %-10s tokens %2u cfg RW%u T%-2u S%u GRF%u O%u : %s\n",c.name,tokens,RW,T,S,GRF,O,bad?"FAIL":"ok");return bad?1:0;
}
template<class F> int all(sycl::queue& q,const Case& c,uint32_t tokens,const uint8_t* w,const float* x,const std::vector<float>& want){
 int f=0;
 if(std::getenv("TEST_ALL")){
 f+=run<F,2,8,4,128>(q,c,tokens,w,x,want);f+=run<F,1,16,4,128>(q,c,tokens,w,x,want);f+=run<F,2,16,4,256>(q,c,tokens,w,x,want);
 f+=run<F,1,32,4,256>(q,c,tokens,w,x,want);f+=run<F,4,8,4,256>(q,c,tokens,w,x,want);f+=run<F,4,16,4,256>(q,c,tokens,w,x,want);
 f+=run<F,1,4,4,128>(q,c,tokens,w,x,want);f+=run<F,2,4,4,128>(q,c,tokens,w,x,want);f+=run<F,1,1,4,128>(q,c,tokens,w,x,want);
 f+=run<F,8,4,4,256>(q,c,tokens,w,x,want);f+=run<F,4,8,4,256,1>(q,c,tokens,w,x,want);f+=run<F,2,16,4,256,1>(q,c,tokens,w,x,want);
 }
 // production list (prefill_reuse2_op.hpp REUSE2_CONFIGS)
 f+=run<F,1,32,4,256>(q,c,tokens,w,x,want);f+=run<F,4,8,4,256>(q,c,tokens,w,x,want);f+=run<F,1,4,4,128>(q,c,tokens,w,x,want);
 f+=run<F,1,1,4,128>(q,c,tokens,w,x,want);f+=run<F,2,16,4,256,1>(q,c,tokens,w,x,want);
 return f;
}
int main(){
 auto dev=sycl::device(sycl::cpu_selector_v);printf("device: %s\n",dev.get_info<sycl::info::device::name>().c_str());
 sycl::queue q(dev,sycl::property::queue::in_order());
 std::mt19937 g(1234);std::uniform_int_distribution<int> byte(0,255);
 auto fill_random=[&](uint8_t* p,size_t n){for(size_t i=0;i<n;++i)p[i]=uint8_t(byte(g));};
 std::vector<Case> cases;
 auto blockcase=[&](const char* name,unsigned T,uint32_t bytes){
  return Case{name,37,2560,uint32_t(10*bytes),[=,&fill_random](std::mt19937& gg,uint8_t* r){fill_random(r,10*bytes);for(int b=0;b<10;++b){uint8_t* p=r+b*bytes;uint16_t d=rhalf(gg);std::memcpy(p,&d,2);if(T!=23){uint16_t m=rhalf(gg);std::memcpy(p+2,&m,2);}}},nullptr};};
 int fails=0;
 auto go=[&](Case c,auto fmt,uint32_t tokens){
  using F=decltype(fmt);
  uint8_t* w=sycl::malloc_shared<uint8_t>(size_t(c.rows)*c.rb+64,q);float* x=sycl::malloc_shared<float>(size_t(tokens)*c.k,q);
  for(uint32_t r=0;r<c.rows;++r)c.fill_row(g,w+size_t(r)*c.rb);
  std::uniform_real_distribution<float> u(-1.f,1.f);std::uniform_int_distribution<int> ex(-6,6);
  for(size_t i=0;i<size_t(tokens)*c.k;++i)x[i]=std::ldexp(u(g),ex(g));
  std::vector<float> want(size_t(tokens)*c.rows);
  for(uint32_t t=0;t<tokens;++t)for(uint32_t r=0;r<c.rows;++r){float s[32];for(unsigned l=0;l<32;++l)s[l]=c.ref(w+size_t(r)*c.rb,x+size_t(t)*c.k,c.k,l);want[size_t(t)*c.rows+r]=tree(s);}
  fails+=all<F>(q,c,tokens,w,x,want);sycl::free(w,q);sycl::free(x,q);
 };
 for(uint32_t tokens:{32u,13u}){
  {Case c=blockcase("Q4_K",12,144);c.ref=[](auto w,auto x,auto k,auto l){return ref_block<12>(w,x,k,l);};go(c,reuse2::Block32<12,BE>{},tokens);}
  {Case c=blockcase("Q5_K",13,176);c.ref=[](auto w,auto x,auto k,auto l){return ref_block<13>(w,x,k,l);};go(c,reuse2::Block32<13,BE>{},tokens);}
  {Case c=blockcase("IQ4_XS",23,136);c.ref=[](auto w,auto x,auto k,auto l){return ref_block<23>(w,x,k,l);};go(c,reuse2::Block32<23,BE>{},tokens);}
  for(uint32_t K:{2560u,6144u}){
   const uint32_t rb6=K+4*(K/16)+18*(K/256),rb8=K+4*(K/32)+4*(K/256)*0;
   auto fillexp=[&,K](uint32_t G){return [=,&fill_random](std::mt19937& gg,uint8_t* r){fill_random(r,K);std::uniform_real_distribution<float> u(0.0001f,0.02f);for(uint32_t i=0;i<K/G;++i){float s=u(gg);std::memcpy(r+K+4*i,&s,4);}};};
   {Case c{"Q6exp",37,K,rb6,fillexp(16),[](auto w,auto x,auto k,auto l){return ref_expanded<16>(w,x,k,l);}};go(c,reuse2::Expanded8<16>{},tokens);}
   {Case c{"Q8exp",37,K,rb8,fillexp(32),[](auto w,auto x,auto k,auto l){return ref_expanded<32>(w,x,k,l);}};go(c,reuse2::Expanded8<32>{},tokens);}
  }
  for(uint32_t K:{320u,2560u,10240u}){
   Case c{"BF16",37,K,K*2,[=](std::mt19937& gg,uint8_t* r){std::uniform_real_distribution<float> u(-0.1f,0.1f);for(uint32_t i=0;i<K;++i){float f=u(gg);uint32_t b;std::memcpy(&b,&f,4);uint16_t h=uint16_t(b>>16);std::memcpy(r+2*i,&h,2);}},ref_bf16};
   go(c,reuse2::BF16x8{},tokens);
  }
  {Case c{"Q6raw",37,2560,10*210,[&](std::mt19937& gg,uint8_t* r){fill_random(r,2100);for(int b=0;b<10;++b){uint16_t d=rhalf(gg);std::memcpy(r+b*210+208,&d,2);}},ref_raw<Type::Q6_K>};go(c,reuse2::Decode8<Q6D>{},tokens);}
  {Case c{"Q8raw",37,640,20*34,[&](std::mt19937& gg,uint8_t* r){fill_random(r,680);for(int b=0;b<20;++b){uint16_t d=rhalf(gg);std::memcpy(r+b*34,&d,2);}},ref_raw<Type::Q8_0>};go(c,reuse2::Decode8<Q8D>{},tokens);}
 }
 printf("TOTAL FAILS %d\n",fails);return fails?1:0;
}
