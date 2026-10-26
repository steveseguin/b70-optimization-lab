// IQ4_NL routed expert down GEMV (10 slots x 2560 rows x K=640, F32 activations): engine replica of
// kopt::MultiplyBlockRows<2> (decode8<IQ4_NL> from the engine's own reference.hpp) against "packed logical lanes"
// variants: one work-item computes the 4 logical lanes 4t..4t+3 of the engine mapping (= one IQ4_NL block per
// 256-column chunk), with each logical lane's accumulation order unchanged (8 consecutive products per chunk, chunks in
// order), then the first two tree levels in registers ((l0+l1)+(l2+l3)) and the remaining three by shuffles.
// Every variant must be bitwise-equal to the replica.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet6-kopt/reference.hpp"
#include "harness.hpp"
using iq3::Type;using iq3::Route;
constexpr unsigned K=640,ROWS=2560,SLOTS=10,RB=K/32*18;
template<int V> struct KK;
// ---- engine replica: MultiplyBlockRows<R> (F32), copied from packet6-kopt/kernels.cpp ----
template<int V,unsigned R>
sycl::event engine(sycl::queue& q,const uint8_t* w,const Route* routes,const float* x,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned SG=32,Subgroups=4;const size_t span=ROWS,rows=ROWS,k=K,rb=RB;
  const size_t blocks=(span+R-1)/R,total=blocks*count,groups=(total+Subgroups-1)/Subgroups;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*Subgroups,SG*Subgroups),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
    const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
    const size_t slot=logical/blocks,first=(logical%blocks)*R;
    Route r=routes[slot];
    const bool valid=iq3::valid_route(r,experts,rows,span);
    if(first==0&&lane==0)status[slot]=valid?0:1;
    const float* xs=x+slot*k;
    float acc[R];const uint8_t* rp[R];bool live[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i){acc[i]=0;const size_t row=first+i;live[i]=valid&&row<span&&row<r.row_count;
      rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*rb:w;}
    const uint32_t k32=uint32_t(k);uint32_t kk=lane*8u;
    for(;kk+8u<=k32;kk+=SG*8u){
      float input[8];
      #pragma unroll
      for(unsigned j=0;j<8;++j)input[j]=xs[kk+j];
      #pragma unroll
      for(unsigned i=0;i<R;++i){
        if(!live[i])continue;float values[8];iq3::kopt::decode8<Type::IQ4_NL>(rp[i],kk,values);
        #pragma unroll
        for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
      }
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){
      float sum=acc[i];
      for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
      const size_t row=first+i;
      if(lane==0&&row<span)y[slot*span+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);
    }
  });
}
// ---- packed variant ----
// SG lanes = SG/8 row sets x 8 items; each item owns RI rows. MODE 0: iq4_level select chain; 1: SLM float[16] table;
// 2: SLM byte-pair table (float2 per byte: low-nibble level, high-nibble level).
template<int V,unsigned SG,unsigned RI,unsigned WGSG,int MODE>
sycl::event packed(sycl::queue& q,const uint8_t* w,const Route* routes,const float* x,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned SETS=SG/8,RPS=SETS*RI;
  const uint32_t span=ROWS,rows=ROWS,k=K,rb=RB;
  const uint32_t blocks=(span+RPS-1)/RPS,total=blocks*count,groups=(total+WGSG-1)/WGSG;
  return q.submit([&](sycl::handler& h){
    sycl::local_accessor<float,1> lut((MODE%10)==2?512:16,h);
    h.parallel_for<KK<V>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(SG)]]{
      if constexpr(MODE%10==1){if(it.get_local_linear_id()<16)lut[it.get_local_linear_id()]=float(iq3::iq4_level(it.get_local_linear_id()));sycl::group_barrier(it.get_group());}
      if constexpr(MODE%10==2){for(unsigned i=it.get_local_linear_id();i<256;i+=SG*WGSG){lut[2*i]=float(iq3::iq4_level(i&15));lut[2*i+1]=float(iq3::iq4_level(i>>4));}sycl::group_barrier(it.get_group());}
      auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
      const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+sg.get_group_linear_id();if(logical>=total)return;
      const uint32_t slot=logical/blocks,first=(logical%blocks)*RPS+set*RI;
      const Route r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,span);
      if(first==0&&lane==0)status[slot]=valid?0:1;
      const float* xs=x+size_t(slot)*k;
      float acc[RI][4];const uint8_t* rp[RI];bool live[RI];
      #pragma unroll
      for(unsigned i=0;i<RI;++i){
        #pragma unroll
        for(unsigned j=0;j<4;++j)acc[i][j]=0;
        const uint32_t row=first+i;live[i]=valid&&row<span&&row<r.row_count;
        rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*rb:w;}
      const bool odd=t&1;
      if constexpr(MODE>=10){
        // all of this item's blocks (K=640: blocks t, t+8, t+16 if t<4) loaded before any decode
        constexpr unsigned NB=3;uint32_t wv[RI][NB][5];
        #pragma unroll
        for(unsigned i=0;i<RI;++i)
          #pragma unroll
          for(unsigned c=0;c<NB;++c){const uint32_t b=t+8u*c;const bool in=live[i]&&b*32u<k;
            const uint32_t* wp=reinterpret_cast<const uint32_t*>(rp[i]+(in?b:0u)*18u-(odd&&in?2:0));
            #pragma unroll
            for(unsigned e=0;e<5;++e)wv[i][c][e]=in?wp[e]:0u;}
        #pragma unroll
        for(unsigned c=0;c<NB;++c){const uint32_t b=t+8u*c;if(b*32u>=k)break;
          float xv[32];
          {const sycl::vec<float,4>* xp=reinterpret_cast<const sycl::vec<float,4>*>(xs+b*32u);
           #pragma unroll
           for(unsigned cc=0;cc<8;++cc){auto v=xp[cc];xv[4*cc]=v[0];xv[4*cc+1]=v[1];xv[4*cc+2]=v[2];xv[4*cc+3]=v[3];}}
          #pragma unroll
          for(unsigned i=0;i<RI;++i){if(!live[i])continue;
            const uint32_t w0=wv[i][c][0],w1=wv[i][c][1],w2=wv[i][c][2],w3=wv[i][c][3],w4=wv[i][c][4];
            const uint32_t sbits=odd?(w0>>16):(w0&0xffffu);uint32_t qw[4];
            qw[0]=odd?w1:(w0>>16)|(w1<<16);qw[1]=odd?w2:(w1>>16)|(w2<<16);qw[2]=odd?w3:(w2>>16)|(w3<<16);qw[3]=odd?w4:(w3>>16)|(w4<<16);
            const float scale=iq3::kopt::half_scale(sbits);
            #pragma unroll
            for(unsigned j=0;j<4;++j){
              #pragma unroll
              for(unsigned jj=0;jj<8;++jj){const unsigned bi=(8*j+jj)%16;const uint32_t byte=(qw[bi/4]>>(8*(bi%4)))&255u;
                float level;if constexpr(MODE==10)level=float(iq3::iq4_level((byte>>(4*(j/2)))&15u));else if constexpr(MODE==11)level=lut[(byte>>(4*(j/2)))&15u];else level=lut[2*byte+(j/2)];
                const float value=scale*level;const float product=value*xv[8*j+jj];acc[i][j]=acc[i][j]+product;}}
          }
        }
      } else
      for(uint32_t b=t;b*32u<k;b+=8u){
        float xv[32];
        {const sycl::vec<float,4>* xp=reinterpret_cast<const sycl::vec<float,4>*>(xs+b*32u);
         #pragma unroll
         for(unsigned c=0;c<8;++c){auto v=xp[c];xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}}
        #pragma unroll
        for(unsigned i=0;i<RI;++i){
          if(!live[i])continue;
          const uint8_t* bs=rp[i]+b*18u;
          const uint32_t* wp=reinterpret_cast<const uint32_t*>(bs-(odd?2:0));
          const uint32_t w0=wp[0],w1=wp[1],w2=wp[2],w3=wp[3],w4=wp[4];
          const uint32_t sbits=odd?(w0>>16):(w0&0xffffu);
          uint32_t qw[4];
          qw[0]=odd?w1:(w0>>16)|(w1<<16);qw[1]=odd?w2:(w1>>16)|(w2<<16);qw[2]=odd?w3:(w2>>16)|(w3<<16);qw[3]=odd?w4:(w3>>16)|(w4<<16);
          const float scale=iq3::kopt::half_scale(sbits);
          #pragma unroll
          for(unsigned j=0;j<4;++j){ // logical lane 4t+j: e=8j..8j+7 -> bytes (8j..8j+7)%16, nibble j/2
            #pragma unroll
            for(unsigned jj=0;jj<8;++jj){
              const unsigned byte_index=(8*j+jj)%16;const uint32_t byte=(qw[byte_index/4]>>(8*(byte_index%4)))&255u;
              float level;
              if constexpr(MODE==0)level=float(iq3::iq4_level((byte>>(4*(j/2)))&15u));
              else if constexpr(MODE==1)level=lut[(byte>>(4*(j/2)))&15u];
              else level=lut[2*byte+(j/2)];
              const float value=scale*level;
              const float product=value*xv[8*j+jj];acc[i][j]=acc[i][j]+product;
            }
          }
        }
      }
      #pragma unroll
      for(unsigned i=0;i<RI;++i){
        const float a01=acc[i][0]+acc[i][1],a23=acc[i][2]+acc[i][3];float sum=a01+a23;
        #pragma unroll
        for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
        const uint32_t row=first+i;
        if(t==0&&row<span)y[size_t(slot)*span+row]=live[i]?sum:iq3::bits_float(0x7fc00000);
      }
    });
  });
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  std::mt19937 g(7);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);
  for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(unsigned b=0;b<K/32;++b){uint8_t* p=&hw[r*RB+b*18];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);
  std::vector<Route> hr;const int ids[10]{3,17,5,29,11,38,2,23,31,7};for(int i=0;i<10;++i)hr.push_back({uint32_t(ids[i]),0,ROWS});
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);
  auto* rt=sycl::malloc_device<Route>(SLOTS,q);auto* st=sycl::malloc_device<uint32_t>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(rt,hr.data(),SLOTS*sizeof(Route)).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);
  engine<0,2>(q,w,rt,x,y,st,experts,SLOTS).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  Bench B(q,y,SLOTS*ROWS);
  B.add("engine MultiplyBlockRows<2> (production)",[&]{return engine<0,2>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine MultiplyBlockRows<1>",[&]{return engine<1,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("packed SG32 RI1 WG4 lut16",[&]{return packed<11,32,1,4,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("packed SG16 RI1 WG4 select-chain",[&]{return packed<13,16,1,4,0>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("packed SG16 RI1 WG4 lut16",[&]{return packed<14,16,1,4,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("packed SG16 RI1 WG4 lut-pair",[&]{return packed<15,16,1,4,2>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("packed SG16 RI2 WG4 lut16",[&]{return packed<16,16,2,4,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("packed SG16 RI1 WG8 lut16",[&]{return packed<17,16,1,8,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("loads-first SG16 RI1 WG4 lut16",[&]{return packed<21,16,1,4,11>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("loads-first SG16 RI1 WG4 lut-pair",[&]{return packed<22,16,1,4,12>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("loads-first SG32 RI1 WG4 lut16",[&]{return packed<23,32,1,4,11>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("loads-first SG16 RI2 WG4 lut16",[&]{return packed<24,16,2,4,11>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("loads-first SG16 RI1 WG4 select",[&]{return packed<25,16,1,4,10>(q,w,rt,x,y,st,experts,SLOTS);});
  B.run();

}
