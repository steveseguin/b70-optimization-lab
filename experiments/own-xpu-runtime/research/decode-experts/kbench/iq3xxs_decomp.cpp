// IQ3_XXS routed expert gate/up GEMV (10 slots x 640 rows x K=2560, F32 activations): engine replica of
// iq3block::BlockRowsOperation<4> against "packed logical lanes" variants: one work-item computes LPI adjacent logical
// lanes of the engine mapping (k = block*256 + group*32 + lane), so the group's grid index byte(s), sign code and
// block scale are decoded once for those lanes. Each logical lane keeps its exact sequence (block, group order; the
// same block_element value; product then add), then the first log2(LPI) tree levels run in registers and the rest by
// shuffles. Every variant must be bitwise-equal to the replica.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <bit>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet2/kernels/grids.hpp"
#include "stage2/packet2/kernels/math.hpp"
#include "harness.hpp"
using iq3::Route;
constexpr unsigned K=2560,ROWS=640,SLOTS=10,RB=K/256*98;
template<int V> struct KK;
// engine block_element_words, verbatim
inline float block_element_words(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const uint32_t index=(uint32_t(reinterpret_cast<const uint16_t*>(b+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
 const auto mag=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
template<int V,unsigned R>
sycl::event engine(sycl::queue& q,const uint8_t* w,const Route* routes,const float* xin,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  const size_t rows=ROWS,columns=K,row_bytes=RB;const size_t blocks=(rows+R-1)/R;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(blocks*count*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
   const auto r=routes[slot];const bool valid=iq3::valid_route(r,experts,uint32_t(rows),uint32_t(rows));
   const float* x=xin+size_t(slot)*columns;float acc[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i)acc[i]=0;
   const uint8_t* rp[R];bool live[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i){const size_t row=first+i;live[i]=valid&&row<rows&&row<r.row_count;rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*row_bytes:w;}
   const uint32_t nblocks=uint32_t(columns/256);
   for(uint32_t block=0;block<nblocks;++block){
    #pragma unroll
    for(unsigned i=0;i<R;++i){if(!live[i])continue;
     const auto*packed=rp[i]+block*98u;const float d=iq3::half(iq3::u16(packed));
     #pragma unroll
     for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;const float weight=block_element_words(packed,d,group,lane);const float product=weight*x[k];acc[i]=acc[i]+product;}}
   }
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<rows)y[size_t(slot)*rows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&status)status[slot]=!valid;
  });
}
// Packed: LPI logical lanes per item (4 or 8), IPR=32/LPI items per row, SETS=SG/IPR row sets per subgroup, RI rows
// per item, WGSG subgroups per work-group.
template<int V,unsigned SG,unsigned LPI,unsigned RI,unsigned WGSG>
sycl::event packed(sycl::queue& q,const uint8_t* w,const Route* routes,const float* xin,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned IPR=32/LPI,SETS=SG/IPR,RPS=SETS*RI;
  const uint32_t rows=ROWS,columns=K,row_bytes=RB;
  const uint32_t blocks=(rows+RPS-1)/RPS,total=blocks*count,groups=(total+WGSG-1)/WGSG;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(SG)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/IPR,m=lane%IPR;
   const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+sg.get_group_linear_id();if(logical>=total)return;
   const uint32_t slot=logical/blocks,first=(logical%blocks)*RPS+set*RI;
   const auto r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,rows);
   const float* x=xin+size_t(slot)*columns;
   float acc[RI][LPI];const uint8_t* rp[RI];bool live[RI];
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    #pragma unroll
    for(unsigned j=0;j<LPI;++j)acc[i][j]=0;
    const uint32_t row=first+i;live[i]=valid&&row<rows&&row<r.row_count;rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*row_bytes:w;}
   const uint32_t nblocks=columns/256u;
   for(uint32_t block=0;block<nblocks;++block){
    float d[RI];
    #pragma unroll
    for(unsigned i=0;i<RI;++i)d[i]=live[i]?iq3::half(iq3::u16(rp[i]+block*98u)):0.f;
    #pragma unroll
    for(unsigned group=0;group<8;++group){
     const uint32_t k0=block*256u+group*32u+m*LPI;
     float xv[LPI];
     #pragma unroll
     for(unsigned c=0;c<LPI/4;++c){const auto v=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0+4*c);xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}
     #pragma unroll
     for(unsigned i=0;i<RI;++i){if(!live[i])continue;
      const uint8_t* b=rp[i]+block*98u;
      const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16;
      // logical lane L=m*LPI+j: code index L/8, sign bit L%8, grid byte L/4, magnitude byte L%4.
      const uint32_t code=(word>>(7*((m*LPI)/8)))&127,mask=code|((std::popcount(code)%2)<<7);
      const float s=(d[i]*(0.5f+float(word>>28)))*0.5f;
      const uint32_t pair=reinterpret_cast<const uint16_t*>(b+2+group*8)[(m*LPI)/8];
      uint32_t grid[LPI/4];
      #pragma unroll
      for(unsigned c=0;c<LPI/4;++c)grid[c]=iq3::iq3_grid[(pair>>(8*(((m*LPI)/4+c)%2)))&255];
      #pragma unroll
      for(unsigned j=0;j<LPI;++j){
       const unsigned L8=(m*LPI+j)%8;
       const uint32_t mag=(grid[j/4]>>(8*(j%4)))&255;
       const int sign=(mask>>L8)&1?-1:1;
       const float weight=(s*float(mag))*float(sign);
       const float product=weight*xv[j];acc[i][j]=acc[i][j]+product;}
     }
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
    if(m==0&&row<rows)y[size_t(slot)*rows+row]=live[i]?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&(logical%blocks)==0&&status)status[slot]=!valid;
  });
}
// Block-hoisted packed variant (LPI=8, RI=1): all of a block's memory reads for this item (scale, 8 sign words, 8 index
// pairs, 16 grid entries) are issued before any of its arithmetic; PF=1 also issues the next block's raw reads first.
template<int V,unsigned SG,unsigned WGSG,int PF>
sycl::event hoisted(sycl::queue& q,const uint8_t* w,const Route* routes,const float* xin,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned LPI=8,IPR=4,SETS=SG/IPR,RPS=SETS;
  const uint32_t rows=ROWS,columns=K,row_bytes=RB;
  const uint32_t blocks=(rows+RPS-1)/RPS,total=blocks*count,groups=(total+WGSG-1)/WGSG;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(SG)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/IPR,m=lane%IPR;
   const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+sg.get_group_linear_id();if(logical>=total)return;
   const uint32_t slot=logical/blocks,row=(logical%blocks)*RPS+set;
   const auto r=routes[slot];const bool valid=iq3::valid_route(r,experts,rows,rows);
   const bool live=valid&&row<rows&&row<r.row_count;
   const uint8_t* rp=live?w+(size_t(r.expert_id)*rows+r.row_begin+row)*row_bytes:w;
   const float* x=xin+size_t(slot)*columns;
   float acc[LPI];
   #pragma unroll
   for(unsigned j=0;j<LPI;++j)acc[j]=0;
   const unsigned L0=m*LPI;
   uint32_t hw[16],pr[8],dh;
   auto fetch=[&](uint32_t block){const uint8_t* bp=rp+block*98u;dh=iq3::u16(bp);const uint16_t* h16=reinterpret_cast<const uint16_t*>(bp+66);
     #pragma unroll
     for(unsigned g=0;g<16;++g)hw[g]=h16[g];
     #pragma unroll
     for(unsigned g=0;g<8;++g)pr[g]=reinterpret_cast<const uint16_t*>(bp+2+g*8)[m];};
   if(live)fetch(0);
   for(uint32_t block=0;block<columns/256u;++block){
    uint32_t chw[16],cpr[8];const uint32_t cdh=dh;
    #pragma unroll
    for(unsigned g=0;g<16;++g)chw[g]=hw[g];
    #pragma unroll
    for(unsigned g=0;g<8;++g)cpr[g]=pr[g];
    if constexpr(PF==1){if(live&&block+1<columns/256u)fetch(block+1);}
    if(!live)continue;
    uint32_t grid[8][2];
    #pragma unroll
    for(unsigned g=0;g<8;++g){grid[g][0]=iq3::iq3_grid[cpr[g]&255];grid[g][1]=iq3::iq3_grid[cpr[g]>>8];}
    const float d=iq3::half(cdh);
    #pragma unroll
    for(unsigned g=0;g<8;++g){
     const uint32_t k0=block*256u+g*32u+L0;float xv[8];
     {const auto v0=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0),v1=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0+4);
      xv[0]=v0[0];xv[1]=v0[1];xv[2]=v0[2];xv[3]=v0[3];xv[4]=v1[0];xv[5]=v1[1];xv[6]=v1[2];xv[7]=v1[3];}
     const uint32_t word=chw[2*g]|(chw[2*g+1]<<16);
     const uint32_t code=(word>>(7*m))&127,mask=code|((std::popcount(code)%2)<<7);
     const float sc=(d*(0.5f+float(word>>28)))*0.5f;
     #pragma unroll
     for(unsigned j=0;j<8;++j){const uint32_t mag=(grid[g][j/4]>>(8*(j%4)))&255;const int sign=(mask>>j)&1?-1:1;
      const float weight=(sc*float(mag))*float(sign);const float product=weight*xv[j];acc[j]=acc[j]+product;}
    }
    if constexpr(PF==0){if(block+1<columns/256u)fetch(block+1);}
   }
   float t[LPI];
   #pragma unroll
   for(unsigned j=0;j<LPI;++j)t[j]=acc[j];
   #pragma unroll
   for(unsigned width=1;width<LPI;width*=2){
    #pragma unroll
    for(unsigned j=0;j<LPI;j+=2*width)t[j]=t[j]+t[j+width];}
   float sum=t[0];
   #pragma unroll
   for(unsigned width=1;width<IPR;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(m%(2*width)==0)sum=sum+rhs;}
   if(m==0&&row<rows)y[size_t(slot)*rows+row]=live?sum:iq3::bits_float(0x7fc00000);
   if(lane==0&&(logical%blocks)==0&&status)status[slot]=!valid;
  });
}
// Decomposition (timing only, WRONG values unless MASK==0): engine BlockRows<4> loop with parts removed.
// MASK bits: 1 = no grid gather (mag from index bits), 2 = no x load (x from lane), 4 = no index load (index from lane),
// 8 = no sign word load (word from block index), 16 = x loaded once per (block,group) outside the row loop.
template<int V,int MASK>
sycl::event decomp(sycl::queue& q,const uint8_t* w,const Route* routes,const float* xin,float* y,uint32_t* status,uint32_t experts,uint32_t count){
  constexpr unsigned R=4;const size_t rows=ROWS,columns=K,row_bytes=RB;const size_t blocks=(rows+R-1)/R;
  return q.parallel_for<KK<V>>(sycl::nd_range<1>(blocks*count*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
   const auto r=routes[slot];const bool valid=iq3::valid_route(r,experts,uint32_t(rows),uint32_t(rows));
   const float* x=xin+size_t(slot)*columns;float acc[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i)acc[i]=0;
   const uint8_t* rp[R];bool live[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i){const size_t row=first+i;live[i]=valid&&row<rows&&row<r.row_count;rp[i]=live[i]?w+(size_t(r.expert_id)*rows+r.row_begin+row)*row_bytes:w;}
   const uint32_t nblocks=uint32_t(columns/256);
   for(uint32_t block=0;block<nblocks;++block){
    float xs[8];
    if constexpr((MASK&16)!=0){
     #pragma unroll
     for(unsigned group=0;group<8;++group)xs[group]=x[block*256u+group*32u+lane];}
    #pragma unroll
    for(unsigned i=0;i<R;++i){if(!live[i])continue;
     const auto*b=rp[i]+block*98u;const float d=iq3::half(iq3::u16(b));
     #pragma unroll
     for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;
      uint32_t word;
      if constexpr((MASK&8)!=0)word=block*0x9e3779b9u+group;else{const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16;}
      const uint32_t code=(word>>(7*(lane/8)))&127;const auto mask=code|((std::popcount(code)%2)<<7);const int sign=(mask>>(lane%8))&1?-1:1;
      uint32_t index;
      if constexpr((MASK&4)!=0)index=(lane*7+group+block)&255;else index=(uint32_t(reinterpret_cast<const uint16_t*>(b+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
      uint32_t entry;if constexpr((MASK&1)!=0)entry=index*0x01010101u;else entry=iq3::iq3_grid[index];
      const auto mag=(entry>>(8*(lane%4)))&255;
      const float weight=(((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
      float xv;if constexpr((MASK&2)!=0)xv=float(lane+group);else if constexpr((MASK&16)!=0)xv=xs[group];else xv=x[k];
      const float product=weight*xv;acc[i]=acc[i]+product;}}
   }
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<rows)y[size_t(slot)*rows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&status)status[slot]=!valid;
  });
}
int main(){
  sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
  std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  std::mt19937 g(5);const int experts=40;std::vector<uint8_t> hw(size_t(experts)*ROWS*RB);for(auto& b:hw)b=uint8_t(g());
  for(size_t r=0;r<size_t(experts)*ROWS;++r)for(unsigned b=0;b<K/256;++b){uint8_t* p=&hw[r*RB+b*98];uint16_t s=uint16_t(0x2000+(g()&0x0fff));p[0]=s&255;p[1]=s>>8;}
  std::vector<float> hx(SLOTS*K);for(auto& v:hx)v=std::uniform_real_distribution<float>(-1,1)(g);
  std::vector<Route> hr;const int ids[10]{3,17,5,29,11,38,2,23,31,7};for(int i=0;i<10;++i)hr.push_back({uint32_t(ids[i]),0,ROWS});
  auto* w=sycl::malloc_device<uint8_t>(hw.size(),q);auto* x=sycl::malloc_device<float>(hx.size(),q);auto* y=sycl::malloc_device<float>(SLOTS*ROWS,q);
  auto* rt=sycl::malloc_device<Route>(SLOTS,q);auto* st=sycl::malloc_device<uint32_t>(SLOTS,q);
  auto* junk=sycl::malloc_device<float>(64*1024*1024,q);
  q.memcpy(w,hw.data(),hw.size()).wait();q.memcpy(x,hx.data(),hx.size()*4).wait();q.memcpy(rt,hr.data(),SLOTS*sizeof(Route)).wait();
  std::vector<float> ref(SLOTS*ROWS),out(SLOTS*ROWS);
  engine<0,4>(q,w,rt,x,y,st,experts,SLOTS).wait();q.memcpy(ref.data(),y,ref.size()*4).wait();
  Bench B(q,y,SLOTS*ROWS);
  B.add("engine BlockRows<4> (production)",[&]{return engine<0,4>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("decomp 0 (replica)",[&]{return decomp<80,0>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("decomp x hoisted out of rows (16)",[&]{return decomp<81,16>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("no grid gather (1)",[&]{return decomp<82,1>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("no x load (2)",[&]{return decomp<83,2>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("no index load (4)",[&]{return decomp<84,4>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("no sign word load (8)",[&]{return decomp<85,8>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("no idx+grid (5)",[&]{return decomp<86,5>(q,w,rt,x,y,st,experts,SLOTS);});
  B.add("no loads but d (15)",[&]{return decomp<87,15>(q,w,rt,x,y,st,experts,SLOTS);});
  B.run();

}
