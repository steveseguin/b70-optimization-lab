#include "p102_expert.hpp"
sycl::event control(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p90exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;return k.submit(q,p,d);}
sycl::event candidate0(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p102::Kernel<2,false> k;return k.submit(q,p,d);}
sycl::event candidate1(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p102::Kernel<4,false> k;return k.submit(q,p,d);}
sycl::event candidate2(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p102::Kernel<1,true> k;return k.submit(q,p,d);}
sycl::event candidate3(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p102::Kernel<2,true> k;return k.submit(q,p,d);}
sycl::event candidate4(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p102::Kernel<4,true> k;return k.submit(q,p,d);}
