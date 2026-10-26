// IQ3_S / IQ2_S routed expert gate (10 slots x 640 rows x K=2560, F32 activations): engine replica of
// kopt::MultiplyBlockRows<4> (decode8 from the engine's reference.hpp) against "packed logical lanes": one work-item
// owns logical lanes 4t..4t+3 (32 consecutive columns of each 256 block), decoding the block's scale/high bits/signs
// once for them. Each logical lane keeps its exact sequence (decode8 values, product then add per 8-chunk, chunks in
// order), then ((l0+l1)+(l2+l3)) in registers and three shuffle levels. Bitwise-equal required.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet6-kopt/reference.hpp"
#include "harness.hpp"
using iq3::Type;using iq3::Route;
constexpr unsigned K=2560,ROWS=640,SLOTS=10;
template<Type T> constexpr unsigned BB=T==Type::IQ3_S?110:82;
template<Type T> constexpr unsigned RB=K/256*BB<T>;
template<int V> struct KK;
template<int V,Type T,unsigned R,unsigned Subgroups=4>
sycl::event engine(sycl::queue& q,const uint8_t* w,const Route* routes,const float* x,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned SG=32;const size_t span=ROWS,rows=ROWS,k=K,rb=RB<T>;
  const size_t blocks=(span+R-1)/R,total=blocks*count,groups=(total+Subgroups-1)/Subgroups;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(groups*SG*Subgroups,SG*Subgroups),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
    const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
    const size_t slot=logical/blocks,first=(logical%blocks)*R;
    Route r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,span);
    if(first==0&&lane==0)status[slot]=valid?0:1;
    const float* xs=x+slot*k;float acc[R];const uint8_t* rp[R];bool live[R];
    #pragma unroll
    for(unsigned i=0;i<R;++i){acc[i]=0;const size_t row=first+i;live[i]=valid&&row<span&&row<r.row_count;rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*rb:w;}
    const uint32_t k32=uint32_t(k);uint32_t kk=lane*8u;
    for(;kk+8u<=k32;kk+=SG*8u){
      float input[8];
      #pragma unroll
      for(unsigned j=0;j<8;++j)input[j]=xs[kk+j];
      #pragma unroll
      for(unsigned i=0;i<R;++i){if(!live[i])continue;float values[8];iq3::kopt::decode8<T>(rp[i],kk,values);
        #pragma unroll
        for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}}
    }
    #pragma unroll
    for(unsigned i=0;i<R;++i){float sum=acc[i];
      for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
      const size_t row=first+i;if(lane==0&&row<span)y[slot*span+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
  });
}
inline uint32_t ld16(const uint8_t* p){return *reinterpret_cast<const uint16_t*>(p);}
// 8 values of logical lane chunk (block b, element e0=8*(4t+j)) exactly as decode8<T>, with per-item hoisted fields.
template<int V,Type T,unsigned SG,unsigned RI,unsigned WGSG>
sycl::event packed(sycl::queue& q,const uint8_t* w,const Route* routes,const float* x,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned SETS=SG/8,RPS=SETS*RI;const uint32_t span=ROWS,rows=ROWS,k=K,rb=RB<T>;
  const uint32_t blocks=(span+RPS-1)/RPS,total=blocks*count,groups=(total+WGSG-1)/WGSG;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(SG)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
    const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+sg.get_group_linear_id();if(logical>=total)return;
    const uint32_t slot=logical/blocks,first=(logical%blocks)*RPS+set*RI;
    const Route r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,span);
    if(first==0&&lane==0)status[slot]=valid?0:1;
    const float* xs=x+size_t(slot)*k;float acc[RI][4];const uint8_t* rp[RI];bool live[RI];
    #pragma unroll
    for(unsigned i=0;i<RI;++i){
      #pragma unroll
      for(unsigned j=0;j<4;++j)acc[i][j]=0;
      const uint32_t row=first+i;live[i]=valid&&row<span&&row<r.row_count;rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*rb:w;}
    for(uint32_t blk=0;blk<k/256u;++blk){
      const uint32_t k0=blk*256u+t*32u;
      float xv[32];
      {const sycl::vec<float,4>* xp=reinterpret_cast<const sycl::vec<float,4>*>(xs+k0);
       #pragma unroll
       for(unsigned c=0;c<8;++c){auto v=xp[c];xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}}
      #pragma unroll
      for(unsigned i=0;i<RI;++i){if(!live[i])continue;
        const uint8_t* b=rp[i]+blk*BB<T>;
        if constexpr(T==Type::IQ3_S){
          // decode8: q=e/4=2l', signs=b[74+l'], sc=(b[106+t/2]>>4*(t%2))&15, scale=half_scale(d)*float(1+2*sc),
          // ix(qi)=b[2+qi]|((b[66+qi/8]>>(qi%8))&1)<<8 with qi=8t+2j+g; v[g*4+jj]=(scale*float(mag))*float(+-1).
          const unsigned sc=(b[106+t/2]>>(4*(t%2)))&15;const float scale=iq3::kopt::half_scale(iq3::u16(b))*float(1+2*sc);
          const uint32_t hi=b[66+t];
          const uint32_t i01=ld16(b+2+8*t),i23=ld16(b+4+8*t),i45=ld16(b+6+8*t),i67=ld16(b+8+8*t);
          const uint32_t s01=ld16(b+74+4*t),s23=ld16(b+76+4*t);
          const uint32_t idx[8]={i01&255,i01>>8,i23&255,i23>>8,i45&255,i45>>8,i67&255,i67>>8};
          const uint32_t sg4[4]={s01&255,s01>>8,s23&255,s23>>8};
          #pragma unroll
          for(unsigned j=0;j<4;++j){
            #pragma unroll
            for(unsigned g=0;g<2;++g){const unsigned qi=2*j+g;const uint32_t ix=idx[qi]|(((hi>>qi)&1)<<8);const uint32_t grid=iq3::iq3_s_grid[ix];
              #pragma unroll
              for(unsigned jj=0;jj<4;++jj){const float value=(scale*float((grid>>(8*jj))&255))*float((sg4[j]>>(g*4+jj))&1?-1:1);
                const float product=value*xv[8*j+4*g+jj];acc[i][j]=acc[i][j]+product;}}
          }
        } else {
          // IQ2_S decode8: q=l'=4t+j, ix=b[2+q]|((b[66+q/4]>>2*(q%4))&3)<<8, signs=b[34+q], sc=(b[74+t]>>4*((j/2)%2))&15,
          // scale=(half_scale(d)*(0.5f+float(sc)))*0.25f, v[jj]=(scale*float(uint32(grid>>8jj&255)))*float(+-1).
          const float d=iq3::kopt::half_scale(iq3::u16(b));const uint32_t scb=b[74+t],hi=b[66+t];
          const uint32_t i01=ld16(b+2+4*t),i23=ld16(b+4+4*t),s01=ld16(b+34+4*t),s23=ld16(b+36+4*t);
          const uint32_t idx[4]={i01&255,i01>>8,i23&255,i23>>8},sg4[4]={s01&255,s01>>8,s23&255,s23>>8};
          #pragma unroll
          for(unsigned j=0;j<4;++j){
            const unsigned sc=(scb>>(4*((j/2)%2)))&15;const float scale=(d*(0.5f+float(sc)))*0.25f;
            const uint32_t ix=idx[j]|(((hi>>(2*j))&3)<<8);const uint64_t grid=iq3::iq2_s_grid[ix];
            const uint32_t glo=uint32_t(grid),ghi=uint32_t(grid>>32);
            #pragma unroll
            for(unsigned jj=0;jj<8;++jj){const float value=(scale*float(((jj<4?glo:ghi)>>(8*(jj%4)))&255))*float((sg4[j]>>jj)&1?-1:1);
              const float product=value*xv[8*j+jj];acc[i][j]=acc[i][j]+product;}
          }
        }
      }
    }
    #pragma unroll
    for(unsigned i=0;i<RI;++i){
      const float a01=acc[i][0]+acc[i][1],a23=acc[i][2]+acc[i][3];float sum=a01+a23;
      #pragma unroll
      for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
      const uint32_t row=first+i;if(t==0&&row<span)y[size_t(slot)*span+row]=live[i]?sum:iq3::bits_float(0x7fc00000);}
  });
}
template<Type T> void bench(sycl::queue& q,const char* name){
  constexpr unsigned rb=RB<T>,bb=BB<T>;
  std::mt19937 g(9);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*rb);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(unsigned b=0;b<K/256;++b){uint8_t* p=&hw[r*rb+b*bb];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);
  std::vector<Route> hr;const int ids[10]{3,17,5,29,11,38,2,23,31,7};for(int i=0;i<10;++i)hr.push_back({uint32_t(ids[i]),0,ROWS});
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);
  auto* rt=sycl::malloc_device<Route>(SLOTS,q);auto* st=sycl::malloc_device<uint32_t>(SLOTS,q);auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(rt,hr.data(),SLOTS*sizeof(Route)).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);
  engine<0+int(T)*100,T,4>(q,w,rt,x,y,st,experts,SLOTS).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  Bench B(q,y,size_t(SLOTS)*ROWS);
  std::printf("%s gate, 10 x 640 x 2560 (%.2f MB), roofline @537 GB/s %.1f us\n",name,SLOTS*ROWS*rb/1e6,SLOTS*ROWS*rb/537e3);
  B.add("engine MultiplyBlockRows<4>",[&]{return engine<0+int(T)*100,T,4>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine R2 WG4",[&]{return engine<10+int(T)*100,T,2>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine R1 WG4",[&]{return engine<11+int(T)*100,T,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine R4 WG1",[&]{return engine<12+int(T)*100,T,4,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine R4 WG8",[&]{return engine<13+int(T)*100,T,4,8>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine R2 WG8",[&]{return engine<14+int(T)*100,T,2,8>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("engine R8 WG4",[&]{return engine<15+int(T)*100,T,8>(q,w,rt,x,y,st,experts,SLOTS);});
  B.run();
  sycl::free(w,q);sycl::free(x,q);sycl::free(y,q);sycl::free(rt,q);sycl::free(st,q);sycl::free(junk,q);
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  bench<Type::IQ3_S>(q,"IQ3_S");bench<Type::IQ2_S>(q,"IQ2_S");
}
