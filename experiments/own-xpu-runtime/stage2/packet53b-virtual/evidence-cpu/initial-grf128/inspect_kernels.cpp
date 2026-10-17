// CPU compile-only entry points. Never built as an executable or launched.
#include "dense_virtual.hpp"
void inspect_kernels(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps){
 p53b::GateKernel gate;gate.submit(q,p,deps);
 p53b::DownKernel down;down.submit(q,p,deps);
 p53b::DenseKernel<iq3::Type::Q8_0,10240,4,2,p39::Kind::silu_div4>{}.submit(q,p,deps);
 p53b::DenseKernel<iq3::Type::Q8_0,10240,4,4,p39::Kind::silu_div4>{}.submit(q,p,deps);
 p53b::DenseKernel<iq3::Type::Q8_0,10240,4,8,p39::Kind::silu_div4>{}.submit(q,p,deps);
 p53b::DenseKernel<iq3::Type::Q8_0,320,1,2,p39::Kind::expert_checks>{}.submit(q,p,deps);
 p53b::DenseKernel<iq3::Type::Q8_0,320,1,4,p39::Kind::expert_checks>{}.submit(q,p,deps);
 p53b::DenseKernel<iq3::Type::Q8_0,320,1,8,p39::Kind::expert_checks>{}.submit(q,p,deps);
 p53b::SmallKernel<2>{}.submit(q,p,deps);
 p53b::SmallKernel<4>{}.submit(q,p,deps);
}
