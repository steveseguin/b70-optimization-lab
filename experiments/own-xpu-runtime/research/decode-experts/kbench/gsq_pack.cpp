// GSQ packed routed experts with the column-interleaved lane mapping (k = lane + 32*n): IQ4_XS gate (10 x 640 x 2560)
// and Q2_0 down (10 x 2560 x 640), F32 activations. Engine replica of gsqn::PackedRowsOperation<T,4> against "packed
// logical lanes": one work-item owns LPI adjacent logical lanes; their quant bytes are one aligned word and the
// group/block scale is computed once. Each logical lane keeps its exact sequence (same element value, product then add,
// same k order), then log2(LPI) tree levels in registers and the rest by shuffles. Bitwise-equal required.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet2/kernels/math.hpp"
#include "gsq-rco-iq3s/integration/build/private/additive/device_formats.hpp"
#include "harness.hpp"
using iq3::Route;
template<int V> struct KK;
template<unsigned T> constexpr size_t ELEM=T==42?64:256;
template<unsigned T> constexpr size_t BYTES=T==42?18:136;
template<int V,unsigned T,unsigned R>
sycl::event engine(sycl::queue& q,const uint8_t* w,const Route* routes,const float* xin,float* y,uint32_t* status,uint32_t experts,uint32_t count,size_t srows,size_t scols){
  const size_t blocks=(srows+R-1)/R,row_bytes=scols/ELEM<T>*BYTES<T>;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(blocks*count*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   constexpr size_t elements=T==42?64:256;constexpr size_t bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
   const auto r=routes[slot];const bool valid=iq3::valid_route(r,experts,uint32_t(srows),uint32_t(srows));
   const float* x=xin+size_t(slot)*scols;float acc[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i)acc[i]=0;
   const uint8_t* rows[R];bool live[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i){const size_t row=first+i;live[i]=valid&&row<srows&&row<r.row_count;rows[i]=live[i]?w+(size_t(r.expert_id)*srows+r.row_begin+row)*row_bytes:w;}
   const uint32_t columns=uint32_t(scols);
   if constexpr(T==42) {
    for(uint32_t block=0;block<columns/64u;++block){
     float d[R];
     #pragma unroll
     for(unsigned i=0;i<R;++i)d[i]=live[i]?iq3::half(iq3::u16(rows[i]+block*18u)):0.f;
     #pragma unroll
     for(unsigned h=0;h<2;++h){const uint32_t e=lane+32u*h,k=block*64u+e;const float input=x[k];
      #pragma unroll
      for(unsigned i=0;i<R;++i){if(!live[i])continue;
       const unsigned code=(rows[i][block*18u+2u+e/4u]>>(2*(e%4u)))&3;const float weight=float(int(code)-1)*d[i];
       const float product=weight*input;acc[i]=acc[i]+product;}}
    }
   } else
   for(uint32_t k=lane;k<columns;k+=32){const float input=x[k];
    #pragma unroll
    for(unsigned i=0;i<R;++i){if(!live[i])continue;
     const float weight=gsq::element_unchecked(T,rows[i]+(k/uint32_t(elements))*uint32_t(bytes),k%uint32_t(elements));const float product=weight*input;acc[i]=acc[i]+product;}}
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<srows)y[size_t(slot)*srows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&status)status[slot]=!valid;
  });
}
template<int V,unsigned T,unsigned SG,unsigned LPI,unsigned RI,unsigned WGSG>
sycl::event packed(sycl::queue& q,const uint8_t* w,const Route* routes,const float* xin,float* y,uint32_t* status,uint32_t experts,uint32_t count,uint32_t srows,uint32_t scols){
  constexpr unsigned IPR=32/LPI,SETS=SG/IPR,RPS=SETS*RI;
  const uint32_t row_bytes=scols/ELEM<T>*BYTES<T>;
  const uint32_t blocks=(srows+RPS-1)/RPS,total=blocks*count,groups=(total+WGSG-1)/WGSG;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(SG)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/IPR,m=lane%IPR;
   const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+sg.get_group_linear_id();if(logical>=total)return;
   const uint32_t slot=logical/blocks,first=(logical%blocks)*RPS+set*RI;
   const auto r=routes[slot];const bool valid=iq3::valid_route(r,experts,srows,srows);
   const float* x=xin+size_t(slot)*scols;
   float acc[RI][LPI];const uint8_t* rp[RI];bool live[RI];
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    #pragma unroll
    for(unsigned j=0;j<LPI;++j)acc[i][j]=0;
    const uint32_t row=first+i;live[i]=valid&&row<srows&&row<r.row_count;rp[i]=live[i]?w+(size_t(r.expert_id)*srows+r.row_begin+row)*row_bytes:w;}
   const unsigned L0=m*LPI;
   if constexpr(T==42){
    for(uint32_t block=0;block<scols/64u;++block){
     float d[RI];
     #pragma unroll
     for(unsigned i=0;i<RI;++i)d[i]=live[i]?iq3::half(iq3::u16(rp[i]+block*18u)):0.f;
     #pragma unroll
     for(unsigned h=0;h<2;++h){
      const uint32_t k0=block*64u+32u*h+L0;float xv[LPI];
      #pragma unroll
      for(unsigned c=0;c<LPI/4;++c){const auto v=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0+4*c);xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}
      #pragma unroll
      for(unsigned i=0;i<RI;++i){if(!live[i])continue;
       // e=L0+j+32h: byte 2+e/4 = 2+L0/4+8h(+j/4), bits 2*(j%4).
       const uint8_t* bp=rp[i]+block*18u+2u+L0/4+8u*h;
       const uint32_t codes=LPI==8?uint32_t(*reinterpret_cast<const uint16_t*>(bp)):uint32_t(*bp);
       #pragma unroll
       for(unsigned j=0;j<LPI;++j){const unsigned code=(codes>>(2*j))&3;const float weight=float(int(code)-1)*d[i];
        const float product=weight*xv[j];acc[i][j]=acc[i][j]+product;}}
     }
    }
   } else { // IQ4_XS (23)
    for(uint32_t n=0;n<scols/32u;++n){
     const uint32_t block=n/8u,group=n%8u,k0=n*32u+L0;float xv[LPI];
     #pragma unroll
     for(unsigned c=0;c<LPI/4;++c){const auto v=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0+4*c);xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}
     #pragma unroll
     for(unsigned i=0;i<RI;++i){if(!live[i])continue;
      const uint8_t* b=rp[i]+block*136u;
      const unsigned scale=((b[4+group/2]>>(4*(group%2)))&15)|(((iq3::u16(b+2)>>(2*group))&3)<<4);
      const float factor=iq3::half(iq3::u16(b))*float(int(scale)-32);
      // i=32*group+L: byte 8+16*group+L%16, nibble L/16; L=L0+j.
      const uint32_t* qp=reinterpret_cast<const uint32_t*>(b+8+16*group+(L0%16));
      uint32_t qw[LPI/4];
      #pragma unroll
      for(unsigned c=0;c<LPI/4;++c)qw[c]=qp[c];
      const unsigned shift=4*(L0/16);
      #pragma unroll
      for(unsigned j=0;j<LPI;++j){const unsigned code=(qw[j/4]>>(8*(j%4)+shift))&15;const float weight=factor*float(iq3::iq4_level(code));
       const float product=weight*xv[j];acc[i][j]=acc[i][j]+product;}}
    }
   }
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    float t[LPI];
    #pragma unroll
    for(unsigned j=0;j<LPI;++j)t[j]=acc[i][j];
    #pragma unroll
    for(unsigned width=1;width<LPI;width*=2){
     #pragma unroll
     for(unsigned j=0;j<LPI;j+=2*width)t[j]=t[j]+t[j+width];}
    float sum=t[0];
    #pragma unroll
    for(unsigned width=1;width<IPR;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(m%(2*width)==0)sum=sum+rhs;}
    const uint32_t row=first+i;
    if(m==0&&row<srows)y[size_t(slot)*srows+row]=live[i]?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&(logical%blocks)==0&&status)status[slot]=!valid;
  });
}
template<unsigned T> void bench(sycl::queue& q,const char* name,uint32_t ROWS,uint32_t K){
  const size_t rb=K/ELEM<T>*BYTES<T>;const unsigned SLOTS=10;
  std::mt19937 g(11);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*rb);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(unsigned b=0;b<K/ELEM<T>;++b){uint8_t* p=&hw[r*rb+b*BYTES<T>];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);
  std::vector<Route> hr;const int ids[10]{3,17,5,29,11,38,2,23,31,7};for(int i=0;i<10;++i)hr.push_back({uint32_t(ids[i]),0,ROWS});
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);
  auto* rt=sycl::malloc_device<Route>(SLOTS,q);auto* st=sycl::malloc_device<uint32_t>(SLOTS,q);auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(rt,hr.data(),SLOTS*sizeof(Route)).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);
  engine<int(T)*100,T,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  Bench B(q,y,size_t(SLOTS)*ROWS);
  std::printf("%s, 10 x %u x %u (%.2f MB), roofline @537 GB/s %.1f us\n",name,ROWS,K,SLOTS*ROWS*rb/1e6,SLOTS*ROWS*rb/537e3);
  B.add("engine PackedRows<4>",[&]{return engine<int(T)*100,T,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.add("packed SG32 LPI4 RI1 WG4",[&]{return packed<int(T)*100+1,T,32,4,1,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.add("packed SG32 LPI4 RI2 WG4",[&]{return packed<int(T)*100+2,T,32,4,2,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.add("packed SG16 LPI4 RI1 WG4",[&]{return packed<int(T)*100+3,T,16,4,1,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.add("packed SG32 LPI8 RI1 WG4",[&]{return packed<int(T)*100+4,T,32,8,1,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.add("packed SG16 LPI8 RI1 WG4",[&]{return packed<int(T)*100+5,T,16,8,1,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.add("packed SG16 LPI8 RI2 WG4",[&]{return packed<int(T)*100+6,T,16,8,2,4>(q,w,rt,x,y,st,experts,SLOTS,ROWS,K);});
  B.run();
  sycl::free(w,q);sycl::free(x,q);sycl::free(y,q);sycl::free(rt,q);sycl::free(st,q);sycl::free(junk,q);
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  bench<23>(q,"IQ4_XS gate",640,2560);bench<42>(q,"Q2_0 down",2560,640);
}
