#include "reference_sort.hpp"
#include <sycl/sycl.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace rr=router_reference_sort;
constexpr int rows=512, width=512, stride=514;
constexpr size_t device_bytes=size_t(rows)*width*4+size_t(rows)*stride*4+rows*4;
static_assert(device_bytes==2103296);
static void need(bool good,const char* why) { if(!good) throw std::runtime_error(why); }
template<class T> static void save(const std::filesystem::path& path,const std::vector<T>& v) {
    std::ofstream f(path,std::ios::binary);
    f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));
    need(bool(f),"output write failed");
}
int main(int argc,char** argv) {
    try {
        need(argc==3,"input512x512.f32 fresh-output-directory");
        const char* selected=std::getenv("FilterBdfPath");
        const char* enabled=std::getenv("OWNRT_REFERENCE_SORT_PROBE");
        need(selected && enabled && std::string(enabled)=="1","explicit device and probe admission");
        std::vector<float> input(size_t(rows)*width);
        std::ifstream file(argv[1],std::ios::binary);
        file.read(reinterpret_cast<char*>(input.data()),input.size()*4);
        need(size_t(file.gcount())==input.size()*4 && file.peek()==EOF,"exact input extent");
        for(float value:input) need(std::isfinite(value),"finite comparator input");
        const std::filesystem::path output=argv[2];
        need(std::filesystem::create_directory(output),"fresh output directory");
        std::vector<int> expected(size_t(rows)*width);
        for(int row=0;row<rows;++row) {
            int* ids=expected.data()+row*width;
            std::iota(ids,ids+width,0);
            const float* score=input.data()+row*width;
            std::sort(ids,ids+width,[&](int a,int b){return score[a]>score[b];});
        }
        save(output/"expected.i32",expected);
        sycl::queue queue(sycl::gpu_selector_v,{sycl::property::queue::in_order()});
        auto device=queue.get_device();
        need(device.has(sycl::aspect::ext_intel_pci_address),"physical PCI identity capability");
        const auto bdf=device.get_info<sycl::ext::intel::info::device::pci_address>();
        need(bdf==selected,"physical device BDF mismatch");
        std::cout<<"bdf="<<bdf<<" device="<<device.get_info<sycl::info::device::name>()
                 <<" explicit_device_bytes="<<device_bytes<<"\n"<<std::flush;
        float* scores=sycl::malloc_device<float>(input.size(),queue);
        int* permutations=sycl::malloc_device<int>(size_t(rows)*stride,queue);
        int* status=sycl::malloc_device<int>(rows,queue);
        need(scores && permutations && status,"bounded device allocation");
        queue.memcpy(scores,input.data(),input.size()*4);
        queue.memset(permutations,0x5a,size_t(rows)*stride*4);
        queue.memset(status,0x5a,rows*4);
        queue.wait_and_throw();
        queue.parallel_for(sycl::range<1>(rows),[=](sycl::id<1> id) {
            const int row=int(id[0]);
            int local_indices[width];
            const bool good=rr::sort_indices(scores+row*width,local_indices,width);
            status[row]=good?0:1;
            if(good) for(int i=0;i<width;++i) permutations[row*stride+1+i]=local_indices[i];
        });
        queue.wait_and_throw();
        std::vector<int> actual(size_t(rows)*stride), flags(rows);
        std::vector<float> unchanged(input.size());
        queue.memcpy(actual.data(),permutations,actual.size()*4);
        queue.memcpy(flags.data(),status,flags.size()*4);
        queue.memcpy(unchanged.data(),scores,unchanged.size()*4);
        queue.wait_and_throw();
        for(void* p:{static_cast<void*>(scores),static_cast<void*>(permutations),static_cast<void*>(status)}) sycl::free(p,queue);
        save(output/"actual-with-canaries.i32",actual);
        save(output/"status.i32",flags);
        save(output/"readback-input.f32",unchanged);
        size_t mismatches=0, invalid=0, canary_errors=0;
        for(int row=0;row<rows;++row) {
            invalid+=flags[row]!=0;
            canary_errors+=actual[row*stride]!=0x5a5a5a5a;
            canary_errors+=actual[row*stride+stride-1]!=0x5a5a5a5a;
            for(int i=0;i<width;++i) mismatches+=actual[row*stride+1+i]!=expected[row*width+i];
        }
        const bool intact=std::memcmp(input.data(),unchanged.data(),input.size()*4)==0;
        const bool passed=!mismatches&&!invalid&&!canary_errors&&intact;
        std::ofstream result(output/"result.json");
        result<<"{\"schema\":\"ownrt.reference-sort-device-probe.v1\",\"passed\":"<<(passed?"true":"false")
              <<",\"rows\":512,\"indices_per_row\":512,\"explicit_device_bytes\":"<<device_bytes
              <<",\"unequal_indices\":"<<mismatches<<",\"invalid_rows\":"<<invalid
              <<",\"canary_errors\":"<<canary_errors<<",\"input_unchanged\":"<<(intact?"true":"false")
              <<",\"private_indices\":true,\"speed_claim\":false}\n";
        need(bool(result),"result write failed");
        return passed?0:1;
    } catch(const std::exception& error) {
        std::cerr<<error.what()<<'\n';
        return 3;
    }
}
