#include "p99_expert.hpp"
sycl::event control(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p65::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;return k.submit(q,p,d);}
sycl::event down_control(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p65::Kernel<iq3::Type::IQ4_NL,640,64,false,true> k;return k.submit(q,p,d);}
sycl::event candidate10(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ2_S,2560,1,false> k;return k.submit(q,p,d);}
sycl::event candidate11(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ2_S,2560,1,true> k;return k.submit(q,p,d);}
sycl::event candidate20(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ2_S,2560,2,false> k;return k.submit(q,p,d);}
sycl::event candidate21(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ2_S,2560,2,true> k;return k.submit(q,p,d);}
sycl::event candidate30(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ2_S,2560,3,false> k;return k.submit(q,p,d);}
sycl::event candidate31(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ2_S,2560,3,true> k;return k.submit(q,p,d);}
sycl::event down_candidate(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p99::Kernel<iq3::Type::IQ4_NL,640,4> k;return k.submit(q,p,d);}
