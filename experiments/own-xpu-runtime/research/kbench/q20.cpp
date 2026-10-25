// Q2_0 routed expert down GEMV microbenchmark (gsqn PackedOperation<42>, 10 slots x 2560 rows x K=640, F32 x), bitwise
// against the engine's lane_sum: lane l owns k=l+32*i, element_unchecked value, product then add, adjacent-pair tree.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
inline uint32_t u16(const uint8_t* b){return uint32_t(b[0])|uint32_t(b[1])<<8;}
inline float bits_float(uint32_t b){return sycl::bit_cast<float>(b);}
inline float half_hw(uint32_t h){uint32_t sign=(h&0x8000)<<16,e=(h>>10)&31,m=h&1023;if(e!=31)return float(sycl::bit_cast<sycl::half>(uint16_t(h)));return bits_float(sign|0x7f800000|(m?0x400000:0));}
inline float element(const uint8_t* b,size_t i){const unsigned code=(b[2+i/4]>>(2*(i%4)))&3;return float(int(code)-1)*half_hw(u16(b));}
constexpr int K=640,ROWS=2560,SLOTS=10,RB=K/64*18;
template<int V> struct KK;
template<int V,int RowsPerSg>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned SG=32;const size_t total=size_t(SLOTS)*ROWS/RowsPerSg;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(total*SG,SG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
    const size_t slot=logical/(ROWS/RowsPerSg),row0=(logical%(ROWS/RowsPerSg))*RowsPerSg;float acc[RowsPerSg];for(int r=0;r<RowsPerSg;++r)acc[r]=0;
    for(size_t k=lane;k<K;k+=32){const float input=x[slot*K+k];
      #pragma unroll
      for(int r=0;r<RowsPerSg;++r){const uint8_t* wr=w+(size_t(expert[slot])*ROWS+row0+r)*RB;const float weight=element(wr+(k/64)*18,k%64);const float product=weight*input;acc[r]=acc[r]+product;}}
    for(int r=0;r<RowsPerSg;++r){float a=acc[r];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,a,(lane+width)%SG);if(lane%(2*width)==0)a=a+rhs;}
      if(lane==0)y[slot*ROWS+row0+r]=a;}});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(13);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(int b=0;b<K/64;++b){uint8_t* p=&hw[r*RB+b*18];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);std::vector<int> he{3,17,5,29,11,38,2,23,31,7};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);auto* e=sycl::malloc_device<int>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),SLOTS*4).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);run<0,1>(q,w,e,x,y).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  auto time=[&](auto fn,const char* label){for(int i=0;i<10;++i)fn().wait();std::vector<double> cold;
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.wait();cold.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
    std::printf("  %-28s cold %7.1f us  %s\n",label,cold[cold.size()/2],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
  std::printf("Q2_0 down, 10 slots x 2560 x 640 (%.1f MB)\n",SLOTS*ROWS*RB/1e6);
  time([&]{return run<0,1>(q,w,e,x,y);},"v0 engine 1 row/sg");
  time([&]{return run<1,2>(q,w,e,x,y);},"v1 2 rows/sg");
  time([&]{return run<2,4>(q,w,e,x,y);},"v2 4 rows/sg");
  time([&]{return run<3,8>(q,w,e,x,y);},"v3 8 rows/sg");
}
