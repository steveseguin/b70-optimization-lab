#include "p82b_recurrence.hpp"
sycl::event recurrence(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p82brec::Kernel<true> k;return k.submit(q,p,d);}
