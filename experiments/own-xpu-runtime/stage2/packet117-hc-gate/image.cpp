// Offline linked Xe2 code inspection only; never executed.
#include "p60_submit.hpp"
#include "hc_gate.hpp"
sycl::event p117_production_image(sycl::queue& q,p60::Bound b,const std::vector<sycl::event>& deps){return p73hc::device(q,b,deps);}
sycl::event p117_candidate_image(sycl::queue& q,p60::Bound b,const std::vector<sycl::event>& deps){return p117hc::device(q,b,deps);}
