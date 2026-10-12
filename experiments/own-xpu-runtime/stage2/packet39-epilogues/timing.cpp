// Coordinator only: this executable was compiled but never run during CPU preparation.
#include "fused_sycl.hpp"
#include "g4_fixture.hpp"
#include "case_runner.hpp"
#include <algorithm>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <numeric>
#include <sstream>
#include <vector>
namespace fs=std::filesystem;
volatile std::sig_atomic_t stopped=0;
void stop(int){stopped=1;}
void check_stop(){if(stopped)throw std::runtime_error("coordinator requested graceful stop");}
std::string quoted(std::string s){std::string r="\"";for(char c:s){if(c=='"'||c=='\\')r+='\\';if(c=='\n'){r+="\\n";continue;}r+=c;}return r+'"';}
void write(const fs::path& p,const std::string& s){std::ofstream f(p);f<<s<<'\n';if(!f)throw std::runtime_error("receipt write failed");}
using p39::Kind;using iq3::Type;
struct DeviceBackend {
 static constexpr bool binding_only=false;
 sycl::queue& q;
 template<class T>T* alloc(size_t n){return sycl::malloc_device<T>(n,q);}
 void copy(void* dst,const void* src,size_t n){q.memcpy(dst,src,n).wait_and_throw();}
 void wait(){q.wait_and_throw();}
 void free(void* p){sycl::free(p,q);}
};
struct Row{std::string label;double groups,control,candidate;unsigned removed,rotations;size_t weight_bytes;bool passed=true;std::string failure_kind,error;};
double median(std::vector<double> x){std::sort(x.begin(),x.end());return(x[(x.size()-1)/2]+x[x.size()/2])/2;}
double event_ms(const std::vector<sycl::event>& es){double n=0;for(auto e:es){e.wait_and_throw();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>(),b=e.get_profiling_info<sycl::info::event_profiling::command_end>();if(b<a)throw std::runtime_error("invalid profiling interval");n+=double(b-a)*1e-6;}return n;}
template<Type T,unsigned K,Kind E,unsigned Split=1>void measure(sycl::queue& q,const fs::path& out,const std::string& name,unsigned rows,double groups,unsigned removed,unsigned repetitions,std::vector<Row>& result,unsigned& gates){
 DeviceBackend backend{q};Fixture<DeviceBackend> f(backend);
 p39::run_case([&]{
  check_stop();f.init<T,K,E>(rows);
  p39::validate<T,K,E,Split>(f.b);
  // Separate GPU comparisons include every surviving raw output, statuses, sticky
  // error, combined streams and activation. Reset is outside measured events.
  for(unsigned scenario=0;scenario<7;++scenario){
   std::vector<uint8_t> reference;
   for(unsigned fused=0;fused<2;++fused){f.reset();uint32_t value=1;
    if(scenario==1){iq3::Route invalid{f.b.experts,0,rows};q.memcpy(const_cast<iq3::Route*>(f.b.routes),&invalid,sizeof invalid).wait_and_throw();}
    if(scenario==2){value=0;q.memcpy(const_cast<uint32_t*>(f.b.active),&value,4).wait_and_throw();}
    if(scenario==3){value=7;q.memcpy(f.b.error,&value,4).wait_and_throw();}
    if(scenario==4){uint16_t nan=0x7fc1;q.memcpy(const_cast<uint16_t*>(f.b.x),&nan,2).wait_and_throw();}
    if(scenario>=5){value=scenario==5?f.b.capacity:UINT32_MAX;q.memcpy(const_cast<uint32_t*>(f.b.position),&value,4).wait_and_throw();}
    auto events=fused?p39::chain<T,K,E,true,Split>(q,f.b):p39::chain<T,K,E,false,Split>(q,f.b);for(auto& e:events)e.wait_and_throw();auto bytes=f.snapshot();
    if(!fused)reference=std::move(bytes);else if(bytes!=reference)throw p39::ByteMismatch("byte mismatch "+name+" scenario "+std::to_string(scenario));
   }
   ++gates;
  }
  // Restore x modified by NaN test before finite timing.
  uint16_t first=iq3::bf16_bits(-8.f/32.f);q.memcpy(const_cast<uint16_t*>(f.b.x),&first,2).wait_and_throw();
  std::vector<double> a,b;
  for(unsigned rep=0;rep<repetitions;++rep){check_stop();
   for(unsigned order=0;order<2;++order){bool fused=(order^(rep&1));unsigned rotation=(rep*2+unsigned(fused))%f.rotations;f.b.w=f.weights[rotation];f.b.peer=f.peers[rotation];f.reset();auto events=fused?p39::chain<T,K,E,true,Split>(q,f.b):p39::chain<T,K,E,false,Split>(q,f.b);double ms=event_ms(events);(fused?b:a).push_back(ms);}
  }
  result.push_back({name,groups,median(a),median(b),removed,f.rotations,f.weight_bytes});
  std::ostringstream raw;raw<<"{\"passed\":true,\"class\":"<<quoted(name)<<",\"control_ms\":[";for(size_t i=0;i<a.size();++i)raw<<(i?",":"")<<std::setprecision(17)<<a[i];raw<<"],\"fused_ms\":[";for(size_t i=0;i<b.size();++i)raw<<(i?",":"")<<std::setprecision(17)<<b[i];raw<<"]}";write(out/(name+".json"),raw.str());
 },[&](const char* kind,const char* message){
  const std::string failure="{\"passed\":false,\"class\":"+quoted(name)+",\"failure_kind\":"+quoted(kind)+",\"error\":"+quoted(message)+"}";
  write(out/(name+".json"),failure);
  result.push_back({name,groups,0,0,removed,f.rotations,f.weight_bytes,false,kind,message});
  if(std::string(kind)=="infrastructure")write(out/"failure.json",failure);
 },[&]{f.release();});
}
int main(int argc,char**argv){
 fs::path out;unsigned card=0,repetitions=200;bool authorized=false,compile_smoke=false;
 try{for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--authorized-device-window")authorized=true;else if(a=="--compile-smoke")compile_smoke=true;else if(a=="--card"&&i+1<argc)card=unsigned(std::stoul(argv[++i]));else if(a=="--output"&&i+1<argc)out=argv[++i];else if(a=="--repetitions"&&i+1<argc)repetitions=unsigned(std::stoul(argv[++i]));else throw std::runtime_error("invalid argument");}
 if(!authorized||out.empty()||repetitions!=200)throw std::runtime_error("authorization, output and exactly 200 repetitions required");fs::create_directories(out);std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 std::vector<sycl::device> devices;for(const auto& d:sycl::device::get_devices(sycl::info::device_type::gpu))if(d.get_backend()==sycl::backend::ext_oneapi_level_zero)devices.push_back(d);
 if(card>=devices.size())throw std::runtime_error("requested Level Zero GPU unavailable");
 sycl::queue q(devices[card],[](sycl::exception_list errors){for(auto& e:errors)std::rethrow_exception(e);},sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
if(compile_smoke){
 auto bundle=sycl::get_kernel_bundle<sycl::bundle_state::executable>(q.get_context(),std::vector<sycl::device>{q.get_device()});
 if(bundle.empty())throw std::runtime_error("empty executable kernel bundle");write(out/"receipt.json","{\"passed\":true,\"compile_smoke\":true,\"device_executed\":false,\"kernel_execution\":false}");return 0;
}
 std::vector<Row> rows;unsigned gates=0;
 g4_cases([&]<Type T,unsigned K,Kind E,unsigned Split>(const char* name,unsigned count,double groups,unsigned removed){measure<T,K,E,Split>(q,out,name,count,groups,removed,repetitions,rows,gates);});
 std::sort(rows.begin(),rows.end(),[](const Row&a,const Row&b){if(a.passed!=b.passed)return a.passed;return(a.control-a.candidate)*a.groups>(b.control-b.candidate)*b.groups;});
 std::ostringstream dispatch;dispatch<<"{\"schema\":\"packet26.dispatch.v1\",\"classes\":{},\"gemv\":{},\"fusions\":{";
 std::ostringstream summary;summary<<std::setprecision(17)<<"{\"schema\":\"packet39.g4.v2\",\"timing_definition\":\"sum of GPU event durations for one launch group (entire chain); median of 200 per arm; ms\",\"rotation_threshold_bytes\":8388608,\"format_counts_from_pinned_runtime_plan\":true,\"rows\":[";
 std::cout<<"class\tstatus\tgroups/token\tunfused ms/group\tfused ms/group\tms/token saved\tweight bytes/buffer\tfull-size banks\n";
 bool first_dispatch=true;unsigned failed=0;
 for(size_t i=0;i<rows.size();++i){auto&r=rows[i];
  summary<<(i?",":"")<<"{\"class\":"<<quoted(r.label)<<",\"passed\":"<<(r.passed?"true":"false")<<",\"groups_per_token\":"<<r.groups<<",\"launches_removed_per_group\":"<<r.removed;
  std::cout<<r.label<<"\t"<<(r.passed?"passed":r.failure_kind)<<"\t"<<r.groups;
  if(r.passed){
   bool paired=r.label.rfind("expert-",0)==0;size_t payload=r.weight_bytes*(paired?2:1);
   if(payload>8*1024*1024 && r.rotations!=8)throw std::runtime_error("full-size rotation required");
   std::cout<<"\t"<<r.control<<"\t"<<r.candidate<<"\t"<<(r.control-r.candidate)*r.groups<<"\t"<<r.weight_bytes<<"\t"<<r.rotations<<"\n";
   dispatch<<(first_dispatch?"":",")<<quoted(r.label)<<":"<<quoted(r.candidate<r.control?"p39.epilogue":"unfused");first_dispatch=false;
   summary<<",\"unfused_ms\":"<<r.control<<",\"fused_ms\":"<<r.candidate<<",\"ms_per_token_saved\":"<<(r.control-r.candidate)*r.groups<<",\"weight_bytes_per_buffer\":"<<r.weight_bytes<<",\"weight_payload_bytes_per_bank\":"<<payload<<",\"rotations\":"<<r.rotations<<",\"rotated_full_size_buffers\":"<<(r.rotations>1?"true":"false")<<",\"buffer_policy\":"<<quoted(r.rotations>1?"eight rotated full-size banks; different control/candidate bank per pair":"single full-size bank; at or below 8 MiB");
  }else{
   ++failed;std::cout<<"\tNA\tNA\tNA\tNA\tNA\n";
   summary<<",\"unfused_ms\":null,\"fused_ms\":null,\"ms_per_token_saved\":null,\"failure_kind\":"<<quoted(r.failure_kind)<<",\"error\":"<<quoted(r.error);
  }
  summary<<"}";
 }
 dispatch<<"}}";summary<<"],\"failed_cases\":"<<failed<<",\"infrastructure_passed\":true}";
 write(out/"dispatch-measured.json",dispatch.str());write(out/"summary.json",summary.str());
 write(out/"receipt.json","{\"passed\":"+std::string(failed?"false":"true")+",\"infrastructure_passed\":true,\"cases_completed\":"+std::to_string(rows.size())+",\"failed_cases\":"+std::to_string(failed)+",\"device_executed\":true,\"repetitions\":200,\"byte_identity_checks\":"+std::to_string(gates)+"}");return 0;
 }catch(const std::exception&e){if(!out.empty()){fs::create_directories(out);if(!fs::exists(out/"failure.json"))write(out/"failure.json","{\"passed\":false,\"error\":"+quoted(e.what())+"}");write(out/"receipt.json","{\"passed\":false}");}std::cerr<<e.what()<<'\n';return 1;}
}
