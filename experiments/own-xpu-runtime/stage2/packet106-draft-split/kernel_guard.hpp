#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
namespace packet26 {
template<class F> inline const unsigned char capture_size[sizeof(F)] __attribute__((used)) = {};
template<class F> F checked(F f) {
 static_assert(sizeof(F)<=1024,"device kernel capture exceeds 1024 bytes");
 (void)capture_size<F>; return f;
}
}
#endif
