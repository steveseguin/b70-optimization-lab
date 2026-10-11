// Coordinator bounding study 4: IQ2_S-like grid decode (10-bit index -> 8 magnitudes, 8 sign bits,
// block scale), comparing a uint64 grid word shifted per weight with byte loads from the table.
// Not an exactness gate and not the real GGUF layout; same row/lane/tile structure as the runtime.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>
static inline float bf16(uint16_t v){ return sycl::bit_cast<float>(uint32_t(v)<<16); }
enum V { grid_u64, grid_bytes, grid_bytes_signfold, COUNT };
static const char* names[]={"grid entry as uint64, shifted per weight (current style)","grid entry read as 8 bytes from the table","8 bytes from the table, sign folded into the integer before the float conversion"};
struct P { const uint8_t* IDX; const uint8_t* QH; const uint8_t* SG; const uint8_t* SC; const uint64_t* G64; const uint8_t* G8; const uint16_t* X; float* Y; size_t rows,K; };
static inline float scale_at(const uint8_t* SC,size_t g){const uint8_t* sp=SC+4*(g/16);uint32_t sb=uint32_t(sp[0])|(uint32_t(sp[1])<<8)|(uint32_t(sp[2])<<16)|(uint32_t(sp[3])<<24);return sycl::bit_cast<float>(sb);}
template<int VV,int WG> sycl::event run(sycl::queue& q,P p){
  size_t groups=(p.rows*32+WG-1)/WG;
  return q.parallel_for(sycl::nd_range<1>(groups*WG,WG),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
    auto sg=it.get_sub_group();size_t row=it.get_group_linear_id()*(WG/32)+sg.get_group_linear_id();unsigned lane=sg.get_local_linear_id();float sum=0;
    if(row<p.rows) for(size_t tile=0;tile<p.K;tile+=256){size_t i=tile+size_t(lane)*8;if(i<p.K){size_t g=row*p.K+i,grp=g/8;
      float sc=scale_at(p.SC,g);unsigned ix=p.IDX[grp]|((unsigned(p.QH[grp/4])>>(2*(grp%4)))&3)<<8;unsigned signs=p.SG[grp];
      if constexpr(VV==grid_u64){uint64_t grid=p.G64[ix];for(unsigned j=0;j<8;++j){int mag=int((grid>>(8*j))&255);float wv=sc*float((signs>>j)&1?-mag:mag);float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
      else if constexpr(VV==grid_bytes){const uint8_t* ge=p.G8+size_t(ix)*8;for(unsigned j=0;j<8;++j){int mag=int(ge[j]);float wv=sc*float((signs>>j)&1?-mag:mag);float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
      else {const uint8_t* ge=p.G8+size_t(ix)*8;for(unsigned j=0;j<8;++j){int mag=int(ge[j]);int sgn=1-2*int((signs>>j)&1);float wv=sc*float(mag*sgn);float pr=wv*bf16(p.X[i+j]);sum=sum+pr;}}
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
  size_t rows=12800,K=2560,n=rows*K,ng=n/8;
  auto* IDX=sycl::malloc_device<uint8_t>(ng+64,q);auto* QH=sycl::malloc_device<uint8_t>(ng/4+64,q);auto* SG=sycl::malloc_device<uint8_t>(ng+64,q);auto* SC=sycl::malloc_device<uint8_t>(n/16*4+64,q);
  auto* G64=sycl::malloc_device<uint64_t>(1024,q);auto* G8=sycl::malloc_device<uint8_t>(8192,q);auto* X=sycl::malloc_device<uint16_t>(K+64,q);auto* Y=sycl::malloc_device<float>(rows*COUNT,q);
  std::vector<uint8_t> hi(ng+64),hq(ng/4+64),hs(ng+64),hsc(n/16*4+64),hg8(8192);std::vector<uint64_t> hg(1024);std::vector<uint16_t> hx(K+64);uint32_t s=777;
  auto rnd=[&]{s=s*1664525u+1013904223u;return s>>8;};
  for(auto&v:hi)v=uint8_t(rnd());for(auto&v:hq)v=uint8_t(rnd());for(auto&v:hs)v=uint8_t(rnd());
  for(size_t b=0;b<n/16;++b){float f=0.01f+float(b%7)*0.003f;std::memcpy(hsc.data()+4*b,&f,4);}
  for(int e=0;e<1024;++e){uint64_t w=0;for(int j=0;j<8;++j){uint8_t m=uint8_t(1+2*(rnd()&3));hg8[e*8+j]=m;w|=uint64_t(m)<<(8*j);}hg[e]=w;}
  for(size_t i=0;i<K;++i)hx[i]=uint16_t(0x3c00+(rnd()&0x3ff));
  q.memcpy(IDX,hi.data(),hi.size()).wait();q.memcpy(QH,hq.data(),hq.size()).wait();q.memcpy(SG,hs.data(),hs.size()).wait();q.memcpy(SC,hsc.data(),hsc.size()).wait();q.memcpy(G64,hg.data(),8192).wait();q.memcpy(G8,hg8.data(),8192).wait();q.memcpy(X,hx.data(),K*2).wait();
  P p{IDX,QH,SG,SC,G64,G8,X,Y,rows,K};
  std::printf("--- expert gate/up shape %zu x %zu (%zu weights), 2.5-bit grid format; the runtime's IQ2_S kernel measures 178 us in the model\n",rows,K,n);
  auto time=[&](auto submit,const char* label){std::vector<double> t;for(int rep=0;rep<15;++rep){sycl::event e=submit();wait(e);t.push_back((e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>())/1000.0);}std::sort(t.begin(),t.end());std::printf("  %-82s %8.1f us  %7.1f G weights/s\n",label,t[t.size()/2],double(n)/t[t.size()/2]/1000.0);};
  time([&]{return run<grid_u64,32>(q,p);},names[grid_u64]);time([&]{return run<grid_bytes,32>(q,p);},names[grid_bytes]);time([&]{return run<grid_bytes_signfold,32>(q,p);},names[grid_bytes_signfold]);
  time([&]{return run<grid_u64,128>(q,p);},"uint64 grid word, four rows per work-group");time([&]{return run<grid_bytes,128>(q,p);},"byte grid loads, four rows per work-group");
  std::vector<float> hy(rows*COUNT);q.memcpy(hy.data(),Y,rows*COUNT*4).wait();
  std::printf("  identical outputs: u64==bytes %d; bytes==signfold %d\n",std::memcmp(hy.data(),hy.data()+rows,rows*4)==0,std::memcmp(hy.data()+rows,hy.data()+2*rows,rows*4)==0);
  for(void* ptr:{(void*)IDX,(void*)QH,(void*)SG,(void*)SC,(void*)G64,(void*)G8,(void*)X,(void*)Y})sycl::free(ptr,q);
  return 0;
}
