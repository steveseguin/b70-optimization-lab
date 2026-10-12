#pragma once
#include <sycl/sycl.hpp>
#include <stdexcept>
inline unsigned p42_compile_smoke(unsigned card) {
#ifdef P42_BINDING_GATE
 // CPU entry traversal only: bundle compilation is an offline/device K0 gate.
 (void)card;return 0;
#else
 std::vector<sycl::device> devices;
 for(auto p:sycl::platform::get_platforms()) if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)
  for(auto d:p.get_devices(sycl::info::device_type::gpu)) devices.push_back(d);
 if(card>=devices.size()) throw std::runtime_error("card unavailable");
 auto d=devices[card];sycl::context c(d);auto ids=sycl::get_kernel_ids();
 if(ids.empty())throw std::runtime_error("no kernels linked");
 auto input=sycl::get_kernel_bundle<sycl::bundle_state::input>(c,{d},ids);
 auto executable=sycl::build(input,{d});
 for(auto id:ids)if(!executable.has_kernel(id,d))throw std::runtime_error("kernel missing after build");
 return ids.size();
#endif
}
