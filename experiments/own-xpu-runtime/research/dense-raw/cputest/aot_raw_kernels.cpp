// AOT-only compile unit (never executed): ISA statistics of the raw decode kernels for bmg-g31.
// icpx -fsycl -std=c++20 -O2 -fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee -fsycl-targets=spir64_gen
//   -Xsycl-target-backend=spir64_gen "-device bmg-g31" -I engine/src aot_raw_kernels.cpp   (IGC_ShaderDumpEnable=1)
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/p33_dense_raw.hpp"
using iq3::Type;
template<Type T,unsigned K,unsigned R,unsigned U,unsigned G> void raw(sycl::queue& q){
 p33::raw::RowsKernel<T,K,R,U,G> k{nullptr,nullptr,nullptr,0,0,0,1};q.parallel_for(sycl::nd_range<1>(128,128),k);
}
int main(int argc,char**){
 if(argc<5)return 0;sycl::queue q;
 raw<Type::Q6_K,2560,1,1,128>(q);raw<Type::Q8_0,6144,1,2,128>(q); // production defaults
 raw<Type::Q6_K,2560,2,1,128>(q);raw<Type::Q6_K,2560,4,1,128>(q);raw<Type::Q6_K,2560,4,2,128>(q);raw<Type::Q6_K,2560,8,1,128>(q);
 raw<Type::Q6_K,2560,4,1,256>(q);raw<Type::Q6_K,2560,4,2,256>(q);raw<Type::Q6_K,2560,8,1,256>(q);raw<Type::Q6_K,2560,8,2,256>(q);
 raw<Type::Q8_0,6144,2,2,128>(q);raw<Type::Q8_0,6144,4,1,128>(q);raw<Type::Q8_0,6144,2,1,128>(q);raw<Type::Q8_0,6144,4,2,256>(q);
 return 0;
}
