#include <sycl/sycl.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include "owner.hpp"
int main(int argc,char** argv){std::filesystem::path out;unsigned first=2,count=2;try {
 bool authorized=false;for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--authorized-device-window")authorized=true;else if(a=="--output"&&i+1<argc)out=argv[++i];else if(a=="--card"&&i+1<argc)first=std::stoul(argv[++i]);else if(a=="--cards"&&i+1<argc)count=std::stoul(argv[++i]);else throw std::runtime_error("K0 argument");}
 if(!authorized||out.empty())throw std::runtime_error("K0 admission/output required");std::filesystem::create_directories(out);
 std::vector<sycl::device> devices;for(auto p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto d:p.get_devices(sycl::info::device_type::gpu))devices.push_back(d);
 if(!count||first+count>devices.size())throw std::runtime_error("K0 card range");
 auto ids=sycl::get_kernel_ids();if(ids.empty())throw std::runtime_error("K0 no kernels linked");
 std::ofstream rows(out/"builds.jsonl");
 for(unsigned i=first;i<first+count;++i){auto d=devices[i];sycl::context context(d);
  // No queue, allocation, command submission or execution. Build every linked image.
  auto input=sycl::get_kernel_bundle<sycl::bundle_state::input>(context,{d},ids);
  auto executable=sycl::build(input,{d});
  for(auto id:ids)if(!executable.has_kernel(id,d))throw std::runtime_error(std::string("missing built kernel: ")+id.get_name());
  rows<<"{\"card\":"<<i<<",\"kernels\":"<<ids.size()<<",\"passed\":true}\n";rows.flush();
 }
 std::ofstream(out/"receipt.json")<<"{\"passed\":true,\"kernel_execution\":false,\"explicit_allocations\":0,\"kernels_per_device\":"<<ids.size()<<",\"cards\":"<<count<<"}\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;if(!out.empty()){std::filesystem::create_directories(out);std::ofstream(out/"failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";}return 1;}}
