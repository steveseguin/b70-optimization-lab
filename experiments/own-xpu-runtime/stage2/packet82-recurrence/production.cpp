#include "p49d_recurrence.hpp"
sycl::event recurrence(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d){p49drec::RecurrenceKernel<4> k;return k.submit(q,p,d);}
