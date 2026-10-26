#pragma once
// OWNRT_DECODE_NEXT2 device bodies (lab 2026-10-26), standalone so the CPU-device tests run the same code as the engine.
#include <sycl/sycl.hpp>
#include <bit>
#include <cstdint>
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet6-kopt/reference.hpp"
namespace dn2 {
using iq3::Type;
// Plain view of one routed IQ3_XXS block launch (gsqn::Bound restated): weights, F32 input per slot, F32 output per slot.
struct XxsView {const uint8_t* w;const float* x;float* y;const iq3::Route* routes;uint32_t* status;uint32_t rows,columns,row_bytes,count,experts;};
// xxs: iq3block::BlockRowsOperation<4> (lane l of a row: column 256*block+32*group+l, blocks then groups in order,
// value (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign), product then add, 32-lane adjacent-pair tree) with
// packed logical lanes. In a 32-lane subgroup, set = lane/8 takes one row (four rows per subgroup, as the original) and
// item t = lane%8 owns logical lanes 4t..4t+3, i.e. columns 32*group+4t..+3 of each block. Per group the four lanes
// share the grid index byte b[2+8*group+t] (one grid word holds their four magnitude bytes), the sign code (lane/8 =
// t/2) and the factor (d*(0.5f+float(word>>28)))*0.5f, computed once with the same operations; each lane's value is
// then (factor*float(mag))*float(sign) and its product and add run in the original order. Tree: ((l0+l1)+(l2+l3)) in
// registers (the first two adjacent-pair levels), then three adjacent-pair levels over the items. The 256-word grid is
// read from a work-group copy (the same words). Inactive rows store NaN, the status word as the original. Same
// work-item count as the original (eight per row).
template<unsigned WGSG> inline void xxs_packed(const XxsView v,sycl::nd_item<1> it){
 constexpr unsigned SG=32,RPS=SG/8;
 uint32_t* grid=*sycl::ext::oneapi::group_local_memory_for_overwrite<uint32_t[256]>(it.get_group());
 for(unsigned li=unsigned(it.get_local_linear_id());li<256;li+=SG*WGSG)grid[li]=iq3::iq3_grid[li];
 sycl::group_barrier(it.get_group());
 const uint32_t blocks=(v.rows+RPS-1)/RPS,total=blocks*v.count;
 const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
 const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=total)return;
 const uint32_t slot=logical/blocks,row=(logical%blocks)*RPS+set;
 const iq3::Route r=v.routes[slot];const bool valid=iq3::valid_route(r,v.experts,v.rows,v.rows);
 const bool live=valid&&row<v.rows&&row<r.row_count;
 const float* x=v.x+size_t(slot)*v.columns;
 const uint8_t* w=live?v.w+(size_t(r.expert_id)*v.rows+r.row_begin+row)*v.row_bytes:v.w;
 float acc[4]={0.f,0.f,0.f,0.f};
 if(live){
  const uint32_t nblocks=v.columns/256;const unsigned cshift=7*(t/2),sbase=4*(t%2);
  for(uint32_t block=0;block<nblocks;++block){
   const uint8_t* packed=w+block*98u;const float d=iq3::half(iq3::u16(packed));
   #pragma unroll
   for(unsigned group=0;group<8;++group){
    const auto*half_words=reinterpret_cast<const uint16_t*>(packed+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16;
    const uint32_t code=(word>>cshift)&127,mask=code|((std::popcount(code)%2)<<7);
    const float scale=(d*(0.5f+float(word>>28)))*0.5f;
    const uint32_t entry=grid[packed[2+group*8+t]];
    const sycl::vec<float,4> xv=*reinterpret_cast<const sycl::vec<float,4>*>(x+block*256u+group*32u+4u*t);
    #pragma unroll
    for(unsigned j=0;j<4;++j){const uint32_t mag=(entry>>(8*j))&255;const int sign=(mask>>(sbase+j))&1?-1:1;
     const float weight=(scale*float(mag))*float(sign);const float product=weight*xv[j];acc[j]=acc[j]+product;}
   }
  }
 }
 const float a01=acc[0]+acc[1],a23=acc[2]+acc[3];float sum=a01+a23;
 #pragma unroll
 for(unsigned width=1;width<8;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
 if(t==0&&row<v.rows)v.y[size_t(slot)*v.rows+row]=live?sum:iq3::bits_float(0x7fc00000);
 if(lane==0&&logical%blocks==0&&v.status)v.status[slot]=!valid;
}
}
