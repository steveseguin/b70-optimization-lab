// IQ4_NL routed expert down GEMV microbenchmark (10 slots x 2560 rows x K=640, F32 activations). Variants must equal the
// engine kopt routed path (v0) bitwise: lane l owns k=l*8+256*i, decode8 values, product then add, adjacent-pair tree.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
inline uint32_t u16(const uint8_t* b){return uint32_t(b[0])|uint32_t(b[1])<<8;}
inline float bits_float(uint32_t b){return sycl::bit_cast<float>(b);}
inline float half_sw(uint32_t h){uint32_t sign=(h&0x8000)<<16,e=(h>>10)&31,m=h&1023;
  if(e==31)return bits_float(sign|0x7f800000|(m?0x400000:0));if(e)return bits_float(sign|((e+112)<<23)|(m<<13));if(!m)return bits_float(sign);
  int exponent=-14;while(!(m&1024)){m<<=1;--exponent;}return bits_float(sign|(uint32_t(exponent+127)<<23)|((m&1023)<<13));}
template<bool HW> inline void decode8(const uint8_t* row,size_t k,float* v){
  auto b=row+(k/32)*18;unsigned i=k%32;float scale;
  if constexpr(HW)scale=float(sycl::bit_cast<sycl::half>(uint16_t(u16(b))));else scale=half_sw(u16(b));
  constexpr int levels[]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
  for(unsigned j=0;j<8;++j)v[j]=scale*float(levels[(b[2+(i+j)%16]>>(4*((i+j)/16)))&15]);}
// Lane decode for 8 consecutive weights at k (k%8==0): their 8 bytes are b[2+(i&15) .. +8] of the block (i=k%32), all
// low nibbles (i<16) or all high nibbles. Two 4-byte loads (aligned or via one extra aligned word) and a packed register
// codebook give the same integer levels as levels[(b[2+(i+j)%16]>>(4*((i+j)/16)))&15].
inline uint32_t load32_a2(const uint8_t* p){ // p is 2-byte aligned
  const uintptr_t a=reinterpret_cast<uintptr_t>(p);if((a&3)==0)return *reinterpret_cast<const uint32_t*>(p);
  const uint32_t* w=reinterpret_cast<const uint32_t*>(a&~uintptr_t(3));return (w[0]>>16)|(w[1]<<16);}
template<bool HW> inline void decode8_words(const uint8_t* row,size_t k,float* v){
  auto b=row+(k/32)*18;unsigned i=k%32;float scale;
  if constexpr(HW)scale=float(sycl::bit_cast<sycl::half>(uint16_t(u16(b))));else scale=half_sw(u16(b));
  const uint8_t* q=b+2+(i&15);const uint32_t lo=load32_a2(q),hi=load32_a2(q+4);const unsigned shift=(i>>4)*4;
  constexpr uint64_t low=0xf6eaddcfbfad9881ull,high=0x7159453526190d01ull;
  for(unsigned j=0;j<8;++j){const unsigned byte=((j<4?lo:hi)>>(8*(j&3)))&255,n=(byte>>shift)&15;
    v[j]=scale*float(int(int8_t(uint8_t(((n<8?low:high)>>(8*(n&7)))&255))));}}
template<unsigned SG> inline void stage_row(const uint8_t* src,uint8_t* dst,size_t n,unsigned lane){
  size_t prefix=(16-(reinterpret_cast<uintptr_t>(src)&15))&15;prefix=prefix<n?prefix:n;
  for(size_t i=lane;i<prefix;i+=SG)dst[i]=src[i];size_t vectors=(n-prefix)/16;auto aligned=reinterpret_cast<const sycl::vec<uint32_t,4>*>(src+prefix);
  for(size_t j=lane;j<vectors;j+=SG){auto bytes=aligned[j].template as<sycl::vec<uint8_t,16>>();for(unsigned i=0;i<16;++i)dst[prefix+j*16+i]=bytes[i];}
  for(size_t i=prefix+vectors*16+lane;i<n;i+=SG)dst[i]=src[i];}
template<int V> struct KK;
constexpr int K=640,ROWS=2560,SLOTS=10,RB=K/32*18;
template<int V,int RowsPerSg>
sycl::event run_rows(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned SG=32,SGS=4;constexpr size_t total=size_t(10)*2560/RowsPerSg,groups=(total+SGS-1)/SGS;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id()*SGS+sg.get_group_linear_id();
    if(logical>=total)return;const size_t slot=logical/(2560/RowsPerSg),row0=(logical%(2560/RowsPerSg))*RowsPerSg;
    float acc[RowsPerSg];for(int r=0;r<RowsPerSg;++r)acc[r]=0;
    for(size_t k=size_t(lane)*8;k<640;k+=SG*8){
      sycl::vec<float,8> xv;xv.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+slot*640+k));
      #pragma unroll
      for(int r=0;r<RowsPerSg;++r){float values[8];decode8_words<false>(w+(size_t(expert[slot])*2560+row0+r)*360,k,values);
        for(unsigned j=0;j<8;++j){float input=xv[j];float product=values[j]*input;acc[r]=acc[r]+product;}}
    }
    for(int r=0;r<RowsPerSg;++r){float a=acc[r];for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,a,(lane+width)%SG);if(lane%(2*width)==0)a=a+rhs;}
      if(lane==0)y[slot*2560+row0+r]=a;}});
}
template<int V,int SGS,bool STAGE,bool HW,bool WORDS=false>
sycl::event run(sycl::queue& q,const uint8_t* w,const int* expert,const float* x,float* y){
  constexpr unsigned SG=32;const size_t total=size_t(SLOTS)*ROWS,groups=(total+SGS-1)/SGS;
  return q.submit([&](sycl::handler& h){sycl::local_accessor<uint8_t,1> storage(STAGE?SGS*368:1,h);
    h.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*SGS,SG*SGS),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
      auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id();
      const size_t logical=it.get_group_linear_id()*SGS+sub;const bool in=logical<total;const size_t slot=logical/ROWS,row=logical%ROWS;
      const uint8_t* src=in?w+(size_t(expert[slot])*ROWS+row)*RB:w;const uint8_t* rowp=src;
      if constexpr(STAGE){auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+sub*368;if(in)stage_row<SG>(src,local,RB,lane);it.barrier(sycl::access::fence_space::local_space);rowp=local;}
      float acc=0;
      if(in)for(size_t k=size_t(lane)*8;k<K;k+=SG*8){float values[8];if constexpr(WORDS)decode8_words<HW>(rowp,k,values);else decode8<HW>(rowp,k,values);for(unsigned j=0;j<8;++j){float input=x[slot*K+k+j];float product=values[j]*input;acc=acc+product;}}
      for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,acc,(lane+width)%SG);if(lane%(2*width)==0)acc=acc+rhs;}
      if(lane==0&&in)y[slot*ROWS+row]=acc;});});
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::mt19937 g(7);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);
  for(size_t i=0;i<hw.size();++i)hw[i]=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(int b=0;b<K/32;++b){uint8_t* p=&hw[r*RB+b*18];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;} // finite small scales
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);std::vector<int> he{3,17,5,29,11,38,2,23,31,7};
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);auto* e=sycl::malloc_device<int>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(e,he.data(),SLOTS*4).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);
  run<0,4,true,false>(q,w,e,x,y).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  auto time=[&](auto fn,const char* label){for(int i=0;i<10;++i)fn().wait();std::vector<double> warm,cold;
    for(int i=0;i<100;++i){auto ev=fn();ev.wait();warm.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    for(int i=0;i<50;++i){q.fill(junk,float(i),64*1024*1024).wait();auto ev=fn();ev.wait();cold.push_back((ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>())/1e3);}
    std::sort(warm.begin(),warm.end());std::sort(cold.begin(),cold.end());q.memcpy(out.data(),y,out.size()*4).wait();
    std::printf("  %-40s warm %7.1f us  cold %7.1f us  %s\n",label,warm[warm.size()/2],cold[cold.size()/2],std::memcmp(out.data(),ref.data(),out.size()*4)?"DIFFERS":"bitwise-equal");};
  std::printf("IQ4_NL down, 10 slots x 2560 x 640 (%.1f MB touched)\n",SLOTS*ROWS*RB/1e6);
  time([&]{return run<0,4,true,false>(q,w,e,x,y);},"v0 engine: stage to SLM, 4 sg/wg");
  time([&]{return run<1,4,false,false>(q,w,e,x,y);},"v1 decode from global, 4 sg/wg");
  time([&]{return run<2,8,false,false>(q,w,e,x,y);},"v2 global, 8 sg/wg");
  time([&]{return run<3,16,false,false>(q,w,e,x,y);},"v3 global, 16 sg/wg");
  time([&]{return run<4,4,false,true>(q,w,e,x,y);},"v4 global, hardware half->float");
  time([&]{return run<5,8,false,true>(q,w,e,x,y);},"v5 global, hw half, 8 sg/wg");
  time([&]{return run<6,4,false,false,true>(q,w,e,x,y);},"v6 global words + register codebook");
  time([&]{return run<7,4,true,false,true>(q,w,e,x,y);},"v7 SLM staged + words + reg codebook");
  time([&]{return run<8,8,false,false,true>(q,w,e,x,y);},"v8 global words + reg codebook, 8 sg");
  time([&]{return run_rows<9,1>(q,w,e,x,y);},"v9 words + vector x load, 1 row/sg");
  time([&]{return run_rows<10,2>(q,w,e,x,y);},"v10 words + vector x, 2 rows/sg");
  time([&]{return run_rows<11,4>(q,w,e,x,y);},"v11 words + vector x, 4 rows/sg");
}
