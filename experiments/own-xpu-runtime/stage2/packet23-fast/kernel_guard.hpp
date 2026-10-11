#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
namespace ownrt { void* submission_parameters(const void*,size_t); }
namespace packet23 {
template<class T> const T* parameters(const T& value){return static_cast<const T*>(ownrt::submission_parameters(&value,sizeof value));}
template<class F> inline const unsigned char capture_size[sizeof(F)] __attribute__((used)) = {};
template<class F> F checked(F f) { static_assert(sizeof(F)<=1024,"device kernel capture exceeds 1024 bytes");(void)capture_size<F>;return f; }
}
#endif
