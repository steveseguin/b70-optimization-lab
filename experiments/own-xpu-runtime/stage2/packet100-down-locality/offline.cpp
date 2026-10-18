// Offline only: actual shipped kernel bodies, no device discovery or main.
#include "p100_down.hpp"
sycl::event production(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p65::Kernel<iq3::Type::IQ4_NL,640,64,false,true> k;return k.submit(q,p,d);}
sycl::event interleave(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p100::Kernel<1> k;return k.submit(q,p,d);}
sycl::event transpose(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p100::Kernel<2> k;return k.submit(q,p,d);}
