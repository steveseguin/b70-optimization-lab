// Actual unfused operation bodies vs the fused bodies, byte checks including scratch.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p33_submit.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/performance.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49d_route.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native/p109_fusion.hpp"
#include <fstream>
#include <filesystem>
#include <iostream>
extern "C" void p109_production_ng(ng::Shape,ng::Args);
static unsigned cases=0;static uint64_t checks=0;
static std::ofstream expected,actual;
template<class T>void compare(const std::vector<T>&a,const std::vector<T>&b,const std::string& label){
 expected.write(reinterpret_cast<const char*>(a.data()),a.size()*sizeof(T));actual.write(reinterpret_cast<const char*>(b.data()),b.size()*sizeof(T));
 if(a.size()!=b.size())throw std::runtime_error(label+" size");
 for(size_t i=0;i<a.size()*sizeof(T);++i){++checks;if(reinterpret_cast<const uint8_t*>(a.data())[i]!=reinterpret_cast<const uint8_t*>(b.data())[i])throw std::runtime_error(label+" byte "+std::to_string(i));}
}
static uint32_t seed=109;static uint32_t next(){seed=1664525*seed+1013904223;return seed;}
static uint16_t finite(){return iq3::bf16_bits(float(int(next()%129)-64)/32.f);}
struct RouteState {
 std::vector<uint32_t> ids=std::vector<uint32_t>(10,99),up=std::vector<uint32_t>(30,99),down=up;
 std::vector<float> prob=std::vector<float>(10,-2.f),scratch=std::vector<float>(1088,-7.f);
 std::vector<uint16_t> act=std::vector<uint16_t>(640,0x1234);uint32_t error=0,active=1,position=0;
 std::vector<void*> pointers(std::vector<uint16_t>&x,std::vector<uint16_t>&g,std::vector<uint16_t>&u){return {x.data(),ids.data(),prob.data(),up.data(),down.data(),scratch.data(),&error,&position,&active,g.data(),u.data(),act.data()};}
};
__attribute__((noinline))static void production_activation(RouteState& a,std::vector<uint16_t>&gate,std::vector<uint16_t>&up){
 ng::Shape s{};s.op=ng::activation;s.width=640;s.extra=1;s.capacity=4096;
 ng::Args b{};b.p[0]=gate.data();b.p[1]=up.data();b.p[2]=a.act.data();b.p[15]=&a.error;b.p[17]=&a.position;b.p[18]=&a.active;
 p109_production_ng(s,b);
}
static void routes(){
 for(unsigned test=0;test<116;++test){
  std::vector<uint16_t>x(512),gate(640),up(640);
  for(unsigned j=0;j<512;++j)x[j]=test%3?finite():iq3::bf16_bits(float(j%13));
  for(unsigned j=0;j<640;++j){gate[j]=uint16_t(test*640+j);up[j]=test%2?finite():uint16_t(65535-(test*640+j)%65536);}
  RouteState a,b;
  if(test==108)a.active=b.active=0;
  if(test==109)a.error=b.error=7;
  if(test==110)a.position=b.position=4096;
  if(test==111)a.position=b.position=0xffffffff;
  if(test>=112)x[test%512]=std::array<uint16_t,4>{0x7f80,0xff80,0x7fc1,0xffa5}[test-112];
  integrated::Spec s{};s.g.h=2560;s.g.mid=640;s.g.top=10;s.g.context=4096;s.ni=1;s.no=4;s.nw=0;s.site.shape[1]=10;s.sizes[0]=512;s.types[0]=flash::Scalar::bf16;s.types[1]=s.types[3]=s.types[4]=flash::Scalar::u32;s.types[2]=flash::Scalar::f32;
  auto pa=a.pointers(x,gate,up),pb=b.pointers(x,gate,up);
  p49droute::host<4,32>(route42::bind(s,std::span<void*const>(pa.data(),9)));production_activation(a,gate,up);
  p109route::Kernel fused;fused.spec=s;fused.run(pb);
  std::string label="route/activation "+std::to_string(test);
  compare(a.ids,b.ids,label);compare(a.up,b.up,label);compare(a.down,b.down,label);compare(a.prob,b.prob,label);compare(a.scratch,b.scratch,label);compare(a.act,b.act,label);compare(std::vector<uint32_t>{a.error,a.active,a.position},std::vector<uint32_t>{b.error,b.active,b.position},label);++cases;
 }
}
struct TailState {
 std::vector<uint16_t> down=std::vector<uint16_t>(2560,0x1234),mix=down,out=down;
 uint32_t error=0,active=1,position=0;
};
__attribute__((noinline))static void production_blend(TailState&a,uint16_t*gate,float*one){
 ng::Shape s{};s.op=ng::moe_combine;s.width=2560;s.extra=1;s.capacity=4096;
 ng::Args b{};b.p[0]=a.mix.data();b.p[1]=one;b.p[2]=a.down.data();b.p[3]=gate;b.p[4]=a.out.data();b.p[15]=&a.error;b.p[17]=&a.position;b.p[18]=&a.active;p109_production_ng(s,b);
}
static void tails(){
 std::vector<uint8_t> weight(2560*760);
 for(unsigned r=0;r<2560;++r){for(unsigned j=0;j<640;++j)weight[r*760+j]=uint8_t(int(next()%31)-15);
  for(unsigned j=0;j<20;++j){float scale=float(next()%16+1)/64.f;std::memcpy(weight.data()+r*760+640+j*4,&scale,4);}}
 for(unsigned test=0;test<28;++test){
  std::vector<uint16_t> input(640),experts(25600);std::vector<float> prob(10);uint16_t gate=finite();float one=1;
  for(auto&v:input)v=finite();for(auto&v:experts)v=finite();for(auto&v:prob)v=float(next()%16)/64.f;
  const std::array<uint16_t,8> exceptional{0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffa5};
  if(test<8)input[test*7]=exceptional[test];
  else if(test<16){experts[(test-8)*2560+3]=exceptional[test-8];gate=exceptional[test-8];}
  else if(test<20)prob[test-16]=std::bit_cast<float>(std::array<uint32_t,4>{0x7f800000,0xff800000,0x7fc12345,0xffa54321}[test-16]);
  TailState a,b;
  if(test==20)a.active=b.active=0;if(test==21)a.error=b.error=7;if(test==22)a.position=b.position=4096;if(test==23)a.position=b.position=0xffffffff;
  if(test>=24){input[0]=exceptional[test-20];experts[0]=exceptional[7-(test-24)];gate=exceptional[test-20];}
  p33::Kernel<0,iq3::Type::Q8_0,640,1> down;down.b.rb=760;down.b.rows=2560;down.b.count=1;down.b.experts=1;down.b.has_routes=false;
  std::array<void*,9> pd{weight.data(),weight.data(),input.data(),a.down.data(),a.down.data(),input.data(),a.down.data(),a.down.data(),a.down.data()};down.run(pd);
  integrated::Combine mixture;mixture.rows=2560;std::array<void*,3> pm{experts.data(),prob.data(),a.mix.data()};mixture.run(pm);production_blend(a,&gate,&one);
  std::array<void*,12> p{weight.data(),input.data(),b.down.data(),experts.data(),prob.data(),b.mix.data(),&gate,&one,b.out.data(),&b.error,&b.position,&b.active};p109::SharedDown fused;fused.capacity=4096;fused.run(p);
  auto label="shared-down/mixture/blend "+std::to_string(test);compare(a.down,b.down,label+" down");compare(a.mix,b.mix,label+" mix");compare(a.out,b.out,label+" output");compare(std::vector<uint32_t>{a.error,a.active,a.position},std::vector<uint32_t>{b.error,b.active,b.position},label);++cases;
 }
 // All BF16 encodings at down/mixture inputs, with a shared-gate palette.
 // This uses finished down values, separating tail arithmetic from the GEMV.
 for(unsigned axis=0;axis<3;++axis)for(unsigned block=0;block<26;++block){
  TailState a,b;std::vector<uint16_t> experts(25600,0);std::vector<float> prob(10,0);prob[0]=1;uint16_t gate=axis==2?uint16_t(block*2519):uint16_t(0x7fc5);float one=1;
  for(unsigned row=0;row<2560;++row){uint16_t value=uint16_t(block*2560+row);a.down[row]=iq3::bf16_bits(iq3::bits_float(uint32_t(axis==0?value:uint16_t(0xffc3))<<16));experts[row]=axis==1?value:uint16_t(0x7fd2);}
  integrated::Combine mixture;mixture.rows=2560;std::array<void*,3> pm{experts.data(),prob.data(),a.mix.data()};mixture.run(pm);production_blend(a,&gate,&one);
  std::array<void*,12> p{weight.data(),nullptr,b.down.data(),experts.data(),prob.data(),b.mix.data(),&gate,&one,b.out.data(),&b.error,&b.position,&b.active};auto bound=p109::bind(p,4096);
  for(unsigned row=0;row<2560;++row){
#if defined(__GNUC__) && !defined(__clang__)
   bound.down[row]=iq3::bf16_bits(iq3::bits_float(uint32_t(a.down[row])<<16));
   bound.mixture[row]=iq3::bf16_bits(iq3::kopt4::combine(bound.experts,bound.probabilities,2560,row));
#else
   p109::tail(bound,row,iq3::bits_float(uint32_t(a.down[row])<<16));
#endif
  }
#if defined(__GNUC__) && !defined(__clang__)
  p109::host_blend(bound);
#endif
  compare(a.down,b.down,"all-bf16 down");compare(a.mix,b.mix,"all-bf16 mix");compare(a.out,b.out,"all-bf16 blend axis="+std::to_string(axis)+" block="+std::to_string(block));++cases;
 }
}
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("output directory");std::filesystem::create_directories(argv[1]);expected.open(std::filesystem::path(argv[1])/"expected.bin",std::ios::binary);actual.open(std::filesystem::path(argv[1])/"actual.bin",std::ios::binary);
 routes();tails();std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases<<",\"byte_checks\":"<<checks<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
