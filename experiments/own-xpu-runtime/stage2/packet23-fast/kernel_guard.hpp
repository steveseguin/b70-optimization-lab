#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
namespace ownrt { void* submission_parameters(const void*,size_t); extern thread_local bool preparing_parameters; extern thread_local bool copy_is_device_to_device; }
namespace packet23 {
template<class F> sycl::event submit(sycl::queue& q,F f){if(ownrt::preparing_parameters)return {};return q.submit(f);}

template<class T> const T* parameters(const T& value){return static_cast<const T*>(ownrt::submission_parameters(&value,sizeof value));}
template<class F> inline const unsigned char capture_size[sizeof(F)] __attribute__((used)) = {};
template<class F> F checked(F f) { static_assert(sizeof(F)<=1024,"device kernel capture exceeds 1024 bytes");(void)capture_size<F>;return f; }
}
#endif
