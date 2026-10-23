// Offline BMG compiler fixture; never called on a device.
#include "p95_expert.hpp"
sycl::event production(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p65::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;return k.submit(q,p,d);}
sycl::event candidate(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p95exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;return k.submit(q,p,d);}
