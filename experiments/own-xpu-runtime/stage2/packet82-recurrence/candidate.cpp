#include "p82_recurrence.hpp"
sycl::event gates(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p82rec::Kernel<false> k;return k.submit(q,p,d);}
sycl::event parallel(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p82rec::Kernel<true> k;return k.submit(q,p,d);}
