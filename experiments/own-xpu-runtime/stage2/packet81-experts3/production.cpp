#include "p65_expert.hpp"
sycl::event gate(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p65::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;return k.submit(q,p,d);}
sycl::event down(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p65::Kernel<iq3::Type::IQ4_NL,640,64,false,true> k;return k.submit(q,p,d);}
