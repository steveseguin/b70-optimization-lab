// Coordinator bounding study (2026-10-11): how fast can a lane/tile GEMV of the runtime's shape run on
// one B70 for different weight encodings and load styles? Not an exactness gate; outputs are checked
// between variants that must agree. One card, small buffers, each submission far below 1 s.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>
static inline float bf16(uint16_t v){ return sycl::bit_cast<float>(uint32_t(v)<<16); }
static inline uint64_t ld64(const uint8_t* p){ uint64_t v; std::memcpy(&v,p,8); return v; }
// IQ4_NL levels as two 64-bit register constants (int8 each), index 0..15.
static constexpr int8_t LV[16]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
static constexpr uint64_t pack(int o){ uint64_t v=0; for(int j=0;j<8;++j) v|=uint64_t(uint8_t(LV[o+j]))<<(8*j); return v; }
static constexpr uint64_t LV0=pack(0), LV1=pack(8);
enum V { int8_naive, int8_wide, nl_naive, nl_wide_regtable, f32_naive, int8_wide_x64, count };
static const char* names[]={"int8 codes, byte loads","int8 codes, one 64-bit code load","IQ4_NL nibbles, byte loads + memory table","IQ4_NL nibbles, 64-bit load + register table","float32 weights","int8 codes + x as two 64-bit loads"};
int main(int argc,char**argv){
  int card=argc>1?std::atoi(argv[1]):0;
  std::vector<sycl::device> ds; for(auto&p:sycl::platform::get_platforms()) if(p.get_backend()==sycl::backend::ext_oneapi_level_zero) for(auto&d:p.get_devices(sycl::info::device_type::gpu)) ds.push_back(d);
  if(card<0||size_t(card)>=ds.size()){std::puts("card");return 2;}
  sycl::queue q(ds[card],sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s card %d\n",ds[card].get_info<sycl::info::device::name>().c_str(),card);
  auto wait=[&](sycl::event e){auto dl=std::chrono::steady_clock::now()+std::chrono::seconds(20);while(e.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){if(std::chrono::steady_clock::now()>dl){std::puts("deadline");std::quick_exit(3);}std::this_thread::sleep_for(std::chrono::microseconds(200));}};
  struct Shape{size_t rows,k;const char*name;}; Shape shapes[]={{12800,2560,"expert gate/up shape 12800 x 2560"},{25600,640,"expert down shape 25600 x 640"},{10240,2560,"gdn.qkv shape 10240 x 2560"}};
  for(auto sh:shapes){
    size_t rows=sh.rows,K=sh.k,n=rows*K;
    auto* W8=sycl::malloc_device<uint8_t>(n+64,q); auto* WN=sycl::malloc_device<uint8_t>(n/2+64,q); auto* WF=sycl::malloc_device<float>(n+16,q);
    auto* X=sycl::malloc_device<uint16_t>(K+64,q); auto* Y=sycl::malloc_device<float>(rows*V::count,q); auto* T=sycl::malloc_device<int8_t>(16,q);
    std::vector<uint8_t> h8(n+64),hn(n/2+64); std::vector<float> hf(n+16); std::vector<uint16_t> hx(K+64); uint32_t s=12345;
    for(size_t i=0;i<n;++i){s=s*1664525u+1013904223u;unsigned c=(s>>24)&15;hn[i/2]|=uint8_t(c<<(4*(i%2)));h8[i]=uint8_t(LV[c]);hf[i]=float(LV[c]);}
    for(size_t i=0;i<K;++i){s=s*1664525u+1013904223u;hx[i]=uint16_t(0x3c00+((s>>20)&0x3ff));}
    q.memcpy(W8,h8.data(),n).wait();q.memcpy(WN,hn.data(),n/2).wait();q.memcpy(WF,hf.data(),n*4).wait();q.memcpy(X,hx.data(),K*2).wait();q.memcpy(T,LV,16).wait();
    std::printf("--- %s (%zu weights)\n",sh.name,n);
    double best[V::count];
    for(int v=0;v<V::count;++v){
      std::vector<double> t;
      for(int rep=0;rep<12;++rep){
        auto e=q.parallel_for(sycl::nd_range<1>(rows*32,32),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
          size_t row=it.get_group_linear_id();unsigned lane=it.get_local_linear_id();auto sg=it.get_sub_group();float sum=0;
          for(size_t tile=0;tile<K;tile+=256){size_t i=tile+size_t(lane)*8;if(i<K){size_t g=row*K+i;
            if(v==int8_naive){for(unsigned j=0;j<8;++j){float p=float(int8_t(W8[g+j]))*bf16(X[i+j]);sum=sum+p;}}
            else if(v==int8_wide){uint64_t w=ld64(W8+g);for(unsigned j=0;j<8;++j){float p=float(int8_t(w>>(8*j)))*bf16(X[i+j]);sum=sum+p;}}
            else if(v==int8_wide_x64){uint64_t w=ld64(W8+g);uint64_t x0=ld64(reinterpret_cast<const uint8_t*>(X+i)),x1=ld64(reinterpret_cast<const uint8_t*>(X+i+4));
              for(unsigned j=0;j<8;++j){uint16_t xv=uint16_t((j<4?x0:x1)>>(16*(j%4)));float p=float(int8_t(w>>(8*j)))*bf16(xv);sum=sum+p;}}
            else if(v==nl_naive){for(unsigned j=0;j<8;++j){unsigned c=(WN[(g+j)/2]>>(4*((g+j)%2)))&15;float p=float(T[c])*bf16(X[i+j]);sum=sum+p;}}
            else if(v==nl_wide_regtable){uint64_t w=ld64(WN+g/2);for(unsigned j=0;j<8;++j){unsigned c=(w>>(4*j))&15;int8_t lv=int8_t((c<8?LV0:LV1)>>(8*(c&7)));float p=float(lv)*bf16(X[i+j]);sum=sum+p;}}
            else {for(unsigned j=0;j<8;++j){float p=WF[g+j]*bf16(X[i+j]);sum=sum+p;}}
          }}
          for(unsigned st=1;st<32;st*=2){float o=sycl::select_from_group(sg,sum,(lane+st)%32);if(lane%(2*st)==0)sum=sum+o;}
          if(lane==0)Y[size_t(v)*rows+row]=sum;});
        wait(e);
        t.push_back((e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>())/1000.0);
      }
      std::sort(t.begin(),t.end());best[v]=t[t.size()/2];
      std::printf("  %-48s median %8.1f us  %7.1f G weights/s\n",names[v],best[v],double(n)/best[v]/1000.0);
    }
    std::vector<float> hy(rows*V::count);q.memcpy(hy.data(),Y,rows*V::count*4).wait();
    auto same=[&](int a,int b){return std::memcmp(hy.data()+size_t(a)*rows,hy.data()+size_t(b)*rows,rows*4)==0;};
    std::printf("  outputs: int8 naive==wide %d, ==wide_x64 %d, ==float32 %d, nibble naive==regtable %d, nibble==int8 %d\n",same(int8_naive,int8_wide),same(int8_naive,int8_wide_x64),same(int8_naive,f32_naive),same(nl_naive,nl_wide_regtable),same(nl_naive,int8_naive));
    for(void* p:{(void*)W8,(void*)WN,(void*)WF,(void*)X,(void*)Y,(void*)T})sycl::free(p,q);
  }
  return 0;
}
