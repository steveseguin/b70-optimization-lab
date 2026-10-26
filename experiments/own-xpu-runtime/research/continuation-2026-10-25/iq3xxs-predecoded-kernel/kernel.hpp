#pragma once
#include <sycl/sycl.hpp>
#include "predecoded.hpp"

namespace iq3_predecoded {
template<bool Cached> class Rows4;
// Standalone microbenchmark entrypoint. Production integration retains the
// existing routed wrapper's range/owner validation and runtime allocation census.
template<bool Cached>
sycl::event submit(sycl::queue& q,const uint8_t* weights,const uint32_t* experts,
                   const float* x,float* y,uint32_t rows,uint32_t columns,uint32_t slots) {
 const size_t cached_stride=row_bytes(columns);
 const size_t stride=Cached?cached_stride:size_t(columns/256)*packed_bytes;
 if(!rows||!slots)throw std::invalid_argument("positive geometry");
 const size_t blocks=(size_t(rows)+3)/4;
 return q.parallel_for<Rows4<Cached>>(sycl::nd_range<1>(blocks*slots*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]] {
  const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
  const size_t logical=it.get_group_linear_id();const uint32_t slot=uint32_t(logical/blocks);
  const size_t first=(logical%blocks)*4;const float* input=x+size_t(slot)*columns;
  float acc[4];const uint8_t* wr[4];
  #pragma unroll
  for(unsigned i=0;i<4;++i){acc[i]=0;wr[i]=first+i<rows?weights+(size_t(experts[slot])*rows+first+i)*stride:weights;}
  for(uint32_t block=0;block<columns/256;++block) {
   #pragma unroll
   for(unsigned i=0;i<4;++i){if(first+i>=rows)continue;
    const auto* p=wr[i]+block*(Cached?cached_bytes:packed_bytes);const float d=iq3::half(iq3::u16(p));
    #pragma unroll
    for(unsigned group=0;group<8;++group){
     const float weight=Cached?element(p,d,group,lane):packed_element_words(p,d,group,lane);
     const float product=weight*input[block*256+group*32+lane];acc[i]=acc[i]+product;
    }
   }
  }
  #pragma unroll
  for(unsigned i=0;i<4;++i){float sum=acc[i];
   for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0&&first+i<rows)y[size_t(slot)*rows+first+i]=sum;
  }
 });
}
}
