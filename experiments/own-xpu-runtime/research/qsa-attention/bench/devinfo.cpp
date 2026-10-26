#include <sycl/sycl.hpp>
#include <cstdio>
int main(){sycl::queue q{sycl::gpu_selector_v};auto d=q.get_device();
std::printf("%s\nCU %u\nlocal_mem %zu\nmax_wg %zu\ngmem_cache %zu line %u\nfreq %u\n",d.get_info<sycl::info::device::name>().c_str(),d.get_info<sycl::info::device::max_compute_units>(),(size_t)d.get_info<sycl::info::device::local_mem_size>(),d.get_info<sycl::info::device::max_work_group_size>(),(size_t)d.get_info<sycl::info::device::global_mem_cache_size>(),d.get_info<sycl::info::device::global_mem_cache_line_size>(),d.get_info<sycl::info::device::max_clock_frequency>());
for(auto s:d.get_info<sycl::info::device::sub_group_sizes>())std::printf("sg %zu\n",s);
try{std::printf("slices %u subslices/slice %u eu/subslice %u simd %u threads/eu %u\n",d.get_info<sycl::ext::intel::info::device::gpu_slices>(),d.get_info<sycl::ext::intel::info::device::gpu_subslices_per_slice>(),d.get_info<sycl::ext::intel::info::device::gpu_eu_count_per_subslice>(),d.get_info<sycl::ext::intel::info::device::gpu_eu_simd_width>(),d.get_info<sycl::ext::intel::info::device::gpu_hw_threads_per_eu>());}catch(...){std::printf("no intel info\n");}
}
