// Coordinator only: this executable was compiled but never run during CPU preparation.
#include "fused_sycl.hpp"
#include "../packet29-merged/arithmetic.hpp"
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
struct Fixture {
 sycl::queue& q;std::vector<void*> allocations;std::vector<std::pair<void*,std::vector<uint8_t>>> initial;
 p39::Bound b{};std::vector<const uint8_t*> weights,peers;size_t weight_bytes=0;unsigned rotations=1;
 template<class T>T* alloc(size_t n){auto p=sycl::malloc_device<T>(n,q);if(!p)throw std::bad_alloc();allocations.push_back(p);return p;}
 template<class T>T* data(std::vector<T> v,bool reset=true){auto p=alloc<T>(v.size());q.memcpy(p,v.data(),v.size()*sizeof(T)).wait_and_throw();if(reset){std::vector<uint8_t> bytes(v.size()*sizeof(T));std::memcpy(bytes.data(),v.data(),bytes.size());initial.push_back({p,std::move(bytes)});}return p;}
 void reset(){for(auto& [p,v]:initial)q.memcpy(p,v.data(),v.size());q.wait_and_throw();}
 std::vector<uint8_t> snapshot(){std::vector<uint8_t> v;for(auto [p,n]:std::vector<std::pair<const void*,size_t>>{{b.y,size_t(b.rows)*b.count*2},{b.py,size_t(b.rows)*b.count*2},{b.out,size_t(b.rows)*b.count*2},{b.streams,size_t(b.rows)*4*2},{b.status,b.count*4},{b.peer_status,b.count*4},{b.error,4},{b.history,size_t(b.rows)*3*2}}){size_t offset=v.size();v.resize(offset+n);q.memcpy(v.data()+offset,p,n).wait_and_throw();}return v;}
 void release(){q.wait_and_throw();for(auto p:allocations)sycl::free(p,q);allocations.clear();}
 Fixture(sycl::queue& queue):q(queue){}
 // No implicit teardown before failure.json is durable. release() is explicit.
 template<Type T,unsigned K,Kind E>void init(unsigned rows){
  constexpr bool paired=E==Kind::expert_act||E==Kind::expert_checks,routed=paired||E==Kind::down_status;
  b.rows=rows;b.count=routed?10:1;b.experts=routed?512:1;
  b.rb=integrated::arithmetic::row_bytes(T,K,(T==Type::Q6_K||T==Type::Q8_0)?6:2);weight_bytes=size_t(b.rb)*b.rows*b.experts;
  rotations=weight_bytes*(paired?2:1)>8*1024*1024?8:1;
  // Entire production bank, not just selected expert rows; rotate complete banks.
  std::vector<uint8_t> host(weight_bytes);uint32_t state=0x39c0ffee;
  for(auto& byte:host){state=state*1664525u+1013904223u;byte=uint8_t(state>>24);}
  unsigned block=T==Type::Q8_0||T==Type::IQ4_NL?32:256;
  unsigned block_bytes=b.rb/(K/block);
  if constexpr(T==Type::Q6_K||T==Type::Q8_0){constexpr unsigned group=T==Type::Q6_K?16:32;for(unsigned row=0;row<b.rows*b.experts;++row)for(unsigned j=0;j<K/group;++j){float scale=0.015625f;std::memcpy(host.data()+size_t(row)*b.rb+K+j*4,&scale,4);}}
  else for(size_t i=0;i<host.size();i+=block_bytes){host[i]=0;host[i+1]=0x24;}
  for(unsigned j=0;j<rotations;++j){auto p=alloc<uint8_t>(host.size());q.memcpy(p,host.data(),host.size()).wait_and_throw();weights.push_back(p);}
  if(paired){for(auto& byte:host)byte^=0x35;for(size_t i=0;i<host.size();i+=block_bytes){host[i]=0;host[i+1]=0x24;}for(unsigned j=0;j<rotations;++j){auto p=alloc<uint8_t>(host.size());q.memcpy(p,host.data(),host.size()).wait_and_throw();peers.push_back(p);}}
  else peers=weights;
  b.w=weights[0];b.peer=peers[0];
  std::vector<uint16_t>x(size_t(K)*(E==Kind::down_status?b.count:1));for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%17)-8)/32.f);
  b.x=data(x,true);size_t n=size_t(rows)*b.count;
  b.y=data(std::vector<uint16_t>(n,0x7e31));b.py=data(std::vector<uint16_t>(n,0x7e32));b.out=data(std::vector<uint16_t>(n,0x7e33));
  b.other=data(std::vector<uint16_t>(n,0x3e80),false);b.mixture=data(std::vector<uint16_t>(n,0x3f00),false);b.shared_gate=data(std::vector<uint16_t>(1,0x3e40),false);
  b.inject=data(std::vector<uint16_t>{0x3f00,0xbe80,0x3e00,0xbf00},false);b.streams=data(std::vector<uint16_t>(rows*4,0x3d80));
  b.status=data(std::vector<uint32_t>(b.count,0));b.peer_status=data(std::vector<uint32_t>(b.count,0));b.error=data(std::vector<uint32_t>(1,0));b.active=data(std::vector<uint32_t>(1,1));
  std::vector<iq3::Route> routes(b.count);for(unsigned i=0;i<b.count;++i)routes[i]={i*37,0,rows};b.routes=data(routes);
  std::vector<float> conv(size_t(rows)*4);for(size_t i=0;i<conv.size();++i)conv[i]=float(int(i%7)-3)/16.f;b.conv_weights=data(conv,false);std::vector<uint16_t> history(size_t(rows)*3);for(size_t i=0;i<history.size();++i)history[i]=iq3::bf16_bits(float(int(i%11)-5)/8.f);b.history=data(history);
  b.scratch=alloc<float>(n*8);b.one=data(std::vector<float>{1.f},false);b.position=data(std::vector<uint32_t>{0},true);
 }
};
struct Row{std::string label;double groups,control,candidate;unsigned removed,rotations;size_t weight_bytes;};
double median(std::vector<double> x){std::sort(x.begin(),x.end());return(x[(x.size()-1)/2]+x[x.size()/2])/2;}
double event_ms(const std::vector<sycl::event>& es){double n=0;for(auto e:es){e.wait_and_throw();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>(),b=e.get_profiling_info<sycl::info::event_profiling::command_end>();if(b<a)throw std::runtime_error("invalid profiling interval");n+=double(b-a)*1e-6;}return n;}
template<Type T,unsigned K,Kind E,unsigned Split=1>void measure(sycl::queue& q,const fs::path& out,const std::string& name,unsigned rows,double groups,unsigned removed,unsigned repetitions,std::vector<Row>& result,unsigned& gates){
 Fixture f(q);
 try{
  check_stop();f.init<T,K,E>(rows);
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
    if(!fused)reference=std::move(bytes);else if(bytes!=reference)throw std::runtime_error("byte mismatch "+name+" scenario "+std::to_string(scenario));
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
  std::ostringstream raw;raw<<"{\"class\":"<<quoted(name)<<",\"control_ms\":[";for(size_t i=0;i<a.size();++i)raw<<(i?",":"")<<std::setprecision(17)<<a[i];raw<<"],\"fused_ms\":[";for(size_t i=0;i<b.size();++i)raw<<(i?",":"")<<std::setprecision(17)<<b[i];raw<<"]}";write(out/(name+".json"),raw.str());f.release();
 }catch(const std::exception& e){write(out/"failure.json","{\"passed\":false,\"class\":"+quoted(name)+",\"error\":"+quoted(e.what())+"}");write(out/"receipt.json","{\"passed\":false,\"device_executed\":true}");f.release();throw;}
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
 measure<Type::IQ2_S,2560,Kind::expert_act>(q,out,"expert-act-iq2",640,47,3,repetitions,rows,gates);
 measure<Type::IQ3_S,2560,Kind::expert_act>(q,out,"expert-act-iq3",640,1,3,repetitions,rows,gates);
 measure<Type::IQ2_S,2560,Kind::expert_checks>(q,out,"expert-checks-iq2",640,47,2,repetitions,rows,gates);
 measure<Type::IQ3_S,2560,Kind::expert_checks>(q,out,"expert-checks-iq3",640,1,2,repetitions,rows,gates);
 measure<Type::IQ4_NL,640,Kind::down_status>(q,out,"down-status",2560,48,1,repetitions,rows,gates);
 measure<Type::Q8_0,10240,Kind::silu_div4,4>(q,out,"hc-low-act",320,97,1,repetitions,rows,gates);
 measure<Type::Q6_K,2560,Kind::shared_act,4>(q,out,"shared-up-act-q6",640,47,1,repetitions,rows,gates);
 measure<Type::Q8_0,2560,Kind::shared_act>(q,out,"shared-up-act-q8",640,1,1,repetitions,rows,gates);
 measure<Type::Q8_0,640,Kind::shared_combine>(q,out,"shared-down-combine",2560,48,2,repetitions,rows,gates);
 measure<Type::Q6_K,2560,Kind::gdn_conv>(q,out,"gdn-qkv-conv-q6",10240,35,1,repetitions,rows,gates);
 measure<Type::Q8_0,2560,Kind::gdn_conv>(q,out,"gdn-qkv-conv-q8",10240,1,1,repetitions,rows,gates);
 measure<Type::Q6_K,6144,Kind::attention_combine,4>(q,out,"attention-combine",2560,48,1,repetitions,rows,gates);
 std::sort(rows.begin(),rows.end(),[](const Row&a,const Row&b){return(a.control-a.candidate)*a.groups>(b.control-b.candidate)*b.groups;});
 std::ostringstream dispatch;dispatch<<"{\"schema\":\"packet26.dispatch.v1\",\"classes\":{},\"gemv\":{},\"fusions\":{";
 std::ostringstream summary;summary<<"{\"schema\":\"packet39.g4.v1\",\"timing_definition\":\"sum of individual GPU event durations per chain, median of 200\",\"format_counts_from_pinned_runtime_plan\":true,\"rows\":[";
 std::cout<<"class\tgroups/token\tunfused ms\tfused ms\tms/token saved\n";
 for(size_t i=0;i<rows.size();++i){auto&r=rows[i];std::cout<<r.label<<"\t"<<r.groups<<"\t"<<r.control<<"\t"<<r.candidate<<"\t"<<(r.control-r.candidate)*r.groups<<"\n";dispatch<<(i?",":"")<<quoted(r.label)<<":"<<quoted(r.candidate<r.control?"p39.epilogue":"unfused");summary<<(i?",":"")<<"{\"class\":"<<quoted(r.label)<<",\"groups_per_token\":"<<r.groups<<",\"launches_removed_per_group\":"<<r.removed<<",\"unfused_ms\":"<<r.control<<",\"fused_ms\":"<<r.candidate<<",\"ms_per_token_saved\":"<<(r.control-r.candidate)*r.groups<<",\"weight_bytes_per_buffer\":"<<r.weight_bytes<<",\"rotations\":"<<r.rotations<<"}";}
 dispatch<<"}}";summary<<"]}";write(out/"dispatch-measured.json",dispatch.str());write(out/"summary.json",summary.str());write(out/"receipt.json","{\"passed\":true,\"device_executed\":true,\"repetitions\":200,\"byte_identity_checks\":"+std::to_string(gates)+"}");return 0;
 }catch(const std::exception&e){if(!out.empty()){fs::create_directories(out);if(!fs::exists(out/"failure.json"))write(out/"failure.json","{\"passed\":false,\"error\":"+quoted(e.what())+"}");write(out/"receipt.json","{\"passed\":false}");}std::cerr<<e.what()<<'\n';return 1;}
}
