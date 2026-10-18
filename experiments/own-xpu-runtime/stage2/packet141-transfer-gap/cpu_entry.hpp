// CPU-only entry into the real device binary. No model, IPC, or SYCL API calls.
// This returns before the ordinary output creation and run_rank boundary.
#include <dlfcn.h>
static int p141_cpu_entry(const Options& a) {
#ifdef OWN_RT_HOST_ONLY
 throw std::runtime_error("p141 CPU entry gate requires the device build's parser");
#else
 require(a.authorized && a.rank>=0 && a.channel>=0 && a.stop_fd>=0 && !a.shared.empty(),
         "p141 CPU entry gate requires actual authorized rank arguments");
 p49d::Selection selected;
 require(!a.selection.empty()&&!a.selection_sha256.empty(),"selection required");
 selected.load(a.selection.string(),a.selection_sha256);
 p141_validate_selection(a,selected);
 // dlopen resolves dependencies only. Never call urInit, zeInit, or SYCL
 // enumeration here; loading the adapter cannot validate physical GPU health.
 for(const char* name:{"libur_adapter_level_zero.so.0","libur_adapter_level_zero_v2.so.0"}) {
  void* handle=dlopen(name,RTLD_NOW|RTLD_LOCAL);
  if(!handle){const char* error=dlerror();throw std::runtime_error(std::string("p141 adapter load: ")+(error?error:name));}
  dlclose(handle);
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"rank\":"<<a.rank
          <<",\"card\":"<<a.card<<",\"authorized\":true,\"selection_sha256\":"
          <<ownrt::quote(selected.observed_sha256)
          <<",\"device_api_called\":false,\"model_read\":false,\"adapter_dependencies_loaded\":true}\n";
 return 0;
#endif
}
