#pragma once
#include "../packet45-merged3/p33_candidates.hpp"
namespace p47gate {
constexpr int rows=12288,cols=2560;
inline const size_t stride=iq3::expanded::row_bytes(iq3::Type::Q6_K,cols);
// Expanded Q6_K fixture: signed bytes followed by FP32 scales per16 weights.
// The same p33.dense.segment lane and adjacent subgroup tree as the control.
inline void cpu(const uint8_t*w,const uint16_t*x,uint16_t*y,int m){for(int t=0;t<m;++t)for(int r=0;r<rows;++r){float a[32];for(int l=0;l<32;++l)a[l]=p33::dense_lane<iq3::Type::Q6_K,cols>(w+r*stride,x+t*cols,0,cols,l);y[t*rows+r]=ng::Args::bits(iq3::tree32(a));}}
inline sycl::event submit(sycl::queue&q,const uint8_t*w,const uint16_t*x,uint16_t*y,int m){const size_t row_stride=stride;return q.submit([&](sycl::handler&handler){handler.parallel_for(sycl::nd_range<1>(size_t(m)*rows*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{int g=it.get_group_linear_id(),r=g%rows,t=g/rows;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id();float value=p33::dense_lane<iq3::Type::Q6_K,cols>(w+r*row_stride,x+t*cols,0,cols,lane);value=p47::lane_tree(sg,value);if(lane==0)y[g]=ng::Args::bits(value);});});}
inline std::vector<uint8_t> weights(){std::vector<uint8_t>w(size_t(rows)*stride);for(int r=0;r<rows;++r){auto*p=w.data()+r*stride;for(int k=0;k<cols;++k)p[k]=uint8_t(int((uint32_t(r)*17+uint32_t(k)*13)%63)-31);for(int k=0;k<cols/16;++k){float scale=float(1+(r+k)%7)/1024.f;std::memcpy(p+cols+k*4,&scale,4);}}return w;}
}
