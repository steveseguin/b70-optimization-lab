// Coordinator bounding study, clean version: every variant is its own compiled kernel (compile-time
// variant), so one variant's code cannot slow another. Not an exactness gate. One card, tiny run.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>
static inline float bf16(uint16_t v){ return sycl::bit_cast<float>(uint32_t(v)<<16); }
static constexpr int8_t LV[16]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
enum V { int8_plain, int8_scale_tile, int8_scale_weight, nib_table_scale_tile, nib_table_scale_weight, f32_plain, COUNT };
static const char* names[]={"int8 codes, no scale","int8 codes x FP32 scale (scale read once per 8 weights)","int8 codes x FP32 scale (scale read per weight)","4-bit codes + 16-entry table x scale (scale once per 8)","4-bit codes + 16-entry table x scale (scale per weight)","float32 weights"};
struct P { const uint8_t* W8; const uint8_t* WN; const float* WF; const uint8_t* SC; const uint16_t* X; float* Y; const int8_t* T; size_t rows,K; };
static inline float scale_at(const uint8_t* SC,size_t g){const uint8_t* sp=SC+4*(g/16);uint32_t sb=uint32_t(sp[0])|(uint32_t(sp[1])<<8)|(uint32_t(sp[2])<<16)|(uint32_t(sp[3])<<24);return sycl::bit_cast<float>(sb);}
template<int VV,int WG> sycl::event run(sycl::queue& q,P p){
  size_t groups=(p.rows*32+WG-1)/WG;
  return q.parallel_for(sycl::nd_range<1>(groups*WG,WG),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
    auto sg=it.get_sub_group();size_t row=it.get_group_linear_id()*(WG/32)+sg.get_group_linear_id();unsigned lane=sg.get_local_linear_id();float sum=0;
    if(row<p.rows) for(size_t tile=0;tile<p.K;tile+=256){size_t i=tile+size_t(lane)*8;if(i<p.K){size_t g=row*p.K+i;
      if constexpr(VV==int8_plain){for(unsigned j=0;j<8;++j){float pr=float(int8_t(p.W8[g+j]))*bf16(p.X[i+j]);sum=sum+pr;}}
      else if constexpr(VV==int8_scale_tile){float sc=scale_at(p.SC,g);for(unsigned j=0;j<8;++j){float wv=sc*float(int8_t(p.W8[g+j]));float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
      else if constexpr(VV==int8_scale_weight){for(unsigned j=0;j<8;++j){float sc=scale_at(p.SC,g+j);float wv=sc*float(int8_t(p.W8[g+j]));float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
      else if constexpr(VV==nib_table_scale_tile){float sc=scale_at(p.SC,g);for(unsigned j=0;j<8;++j){unsigned c=(p.WN[(g+j)/2]>>(4*((g+j)%2)))&15;float wv=sc*float(p.T[c]);float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
      else if constexpr(VV==nib_table_scale_weight){for(unsigned j=0;j<8;++j){float sc=scale_at(p.SC,g+j);unsigned c=(p.WN[(g+j)/2]>>(4*((g+j)%2)))&15;float wv=sc*float(p.T[c]);float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
      else {for(unsigned j=0;j<8;++j){float pr=p.WF[g+j]*bf16(p.X[i+j]);sum=sum+pr;}}
    }}
    for(unsigned st=1;st<32;st*=2){float o=sycl::select_from_group(sg,sum,(lane+st)%32);if(lane%(2*st)==0)sum=sum+o;}
    if(lane==0&&row<p.rows)p.Y[size_t(VV)*p.rows+row]=sum;});
}
int main(int argc,char**argv){
  int card=argc>1?std::atoi(argv[1]):0;
  std::vector<sycl::device> ds; for(auto&pl:sycl::platform::get_platforms()) if(pl.get_backend()==sycl::backend::ext_oneapi_level_zero) for(auto&d:pl.get_devices(sycl::info::device_type::gpu)) ds.push_back(d);
  if(card<0||size_t(card)>=ds.size()){std::puts("card");return 2;}
  sycl::queue q(ds[card],sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s card %d\n",ds[card].get_info<sycl::info::device::name>().c_str(),card);
  auto wait=[&](sycl::event e){auto dl=std::chrono::steady_clock::now()+std::chrono::seconds(20);while(e.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){if(std::chrono::steady_clock::now()>dl){std::puts("deadline");std::quick_exit(3);}std::this_thread::sleep_for(std::chrono::microseconds(200));}};
  struct Shape{size_t rows,k;const char*name;double runtime_us;const char* what;}; Shape shapes[]={{12800,2560,"expert gate/up shape 12800 x 2560",178,"IQ2_S"},{25600,640,"expert down shape 25600 x 640",130,"IQ4_NL"},{10240,2560,"gdn.qkv shape 10240 x 2560",101,"expanded Q6"},{6144,2560,"gdn.z shape 6144 x 2560",62,"expanded Q6"}};
  for(auto sh:shapes){
    size_t rows=sh.rows,K=sh.k,n=rows*K;
    auto* W8=sycl::malloc_device<uint8_t>(n+64,q); auto* WN=sycl::malloc_device<uint8_t>(n/2+64,q); auto* WF=sycl::malloc_device<float>(n+16,q);auto* SC=sycl::malloc_device<uint8_t>(n/16*4+64,q);
    auto* X=sycl::malloc_device<uint16_t>(K+64,q); auto* Y=sycl::malloc_device<float>(rows*COUNT,q); auto* T=sycl::malloc_device<int8_t>(16,q);
    std::vector<uint8_t> h8(n+64),hn(n/2+64),hs(n/16*4+64); std::vector<float> hf(n+16); std::vector<uint16_t> hx(K+64); uint32_t s=12345;
    for(size_t i=0;i<n;++i){s=s*1664525u+1013904223u;unsigned c=(s>>24)&15;hn[i/2]|=uint8_t(c<<(4*(i%2)));h8[i]=uint8_t(LV[c]);hf[i]=float(LV[c]);}
    for(size_t b=0;b<n/16;++b){float f=0.01f+float(b%7)*0.003f;std::memcpy(hs.data()+4*b,&f,4);}
    for(size_t i=0;i<K;++i){s=s*1664525u+1013904223u;hx[i]=uint16_t(0x3c00+((s>>20)&0x3ff));}
    q.memcpy(W8,h8.data(),n).wait();q.memcpy(WN,hn.data(),n/2).wait();q.memcpy(WF,hf.data(),n*4).wait();q.memcpy(X,hx.data(),K*2).wait();q.memcpy(T,LV,16).wait();q.memcpy(SC,hs.data(),hs.size()).wait();
    P p{W8,WN,WF,SC,X,Y,T,rows,K};
    std::printf("--- %s (%zu weights); the runtime's %s kernel measures %.0f us in the model\n",sh.name,n,sh.what,sh.runtime_us);
    auto time=[&](auto submit,const char* label){std::vector<double> t;for(int rep=0;rep<15;++rep){sycl::event e=submit();wait(e);t.push_back((e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>())/1000.0);}std::sort(t.begin(),t.end());std::printf("  %-58s %8.1f us  %7.1f G weights/s\n",label,t[t.size()/2],double(n)/t[t.size()/2]/1000.0);};
#define T2(VV) time([&]{return run<VV,32>(q,p);},names[VV]);
    T2(int8_plain) T2(int8_scale_tile) T2(int8_scale_weight) T2(nib_table_scale_tile) T2(nib_table_scale_weight) T2(f32_plain)
    time([&]{return run<int8_scale_tile,128>(q,p);},"int8 x scale once per 8, four rows per work-group");
    time([&]{return run<nib_table_scale_tile,128>(q,p);},"4-bit + table x scale once per 8, four rows per work-group");
    std::vector<float> hy(rows*COUNT);q.memcpy(hy.data(),Y,rows*COUNT*4).wait();
    auto same=[&](int a,int b){return std::memcmp(hy.data()+size_t(a)*rows,hy.data()+size_t(b)*rows,rows*4)==0;};
    std::printf("  identical outputs: int8 scale once==per weight %d; 4-bit once==per weight %d; 4-bit==int8 %d\n",same(int8_scale_tile,int8_scale_weight),same(nib_table_scale_tile,nib_table_scale_weight),same(nib_table_scale_tile,int8_scale_tile));
    for(void* ptr:{(void*)W8,(void*)WN,(void*)WF,(void*)X,(void*)Y,(void*)T,(void*)SC})sycl::free(ptr,q);
  }
  return 0;
}
