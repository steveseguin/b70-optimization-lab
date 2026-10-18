#include "cases.hpp"
#include <csignal>
#include <atomic>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <openssl/sha.h>
#include <unistd.h>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
using namespace p112test;
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){require(!stopped,"coordinator graceful stop");}
static std::string digest(const void*p,size_t size){unsigned char out[32];SHA256(static_cast<const unsigned char*>(p),size,out);std::ostringstream s;for(auto c:out)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return s.str();}
static std::vector<uint8_t>output_bytes(const State&s){std::vector<uint8_t>b;auto add=[&](const auto&x){auto*p=reinterpret_cast<const uint8_t*>(&x);b.insert(b.end(),p,p+sizeof(x));};add(s.ids);add(s.weights);add(s.up);add(s.down);add(s.error);return b;}
#ifndef OWN_RT_HOST_ONLY
struct DeviceState {
 sycl::queue&q;State*state;void*input;
 DeviceState(sycl::queue&v):q(v){state=sycl::malloc_device<State>(1,q);input=sycl::malloc_device(2048,q);require(state&&input,"allocation failed");}
 ~DeviceState(){q.wait();sycl::free(input,q);sycl::free(state,q);}
 void upload(const State&s,Case&c){q.memcpy(state,&s,sizeof s).wait_and_throw();q.memcpy(input,c.input(),c.bf16?1024:2048).wait_and_throw();}
 State read(){State s;q.memcpy(&s,state,sizeof s).wait_and_throw();return s;}
 std::vector<void*>bindings(unsigned no){
  // Build offsets on host; never dereference a device pointer on the host.
  auto at=[&](size_t n){return static_cast<void*>(reinterpret_cast<uint8_t*>(state)+n);};
  std::vector<void*>p{input,at(offsetof(State,ids)),at(offsetof(State,weights))};
  if(no==4){p.push_back(at(offsetof(State,up)));p.push_back(at(offsetof(State,down)));}
  for(size_t off:{offsetof(State,scratch),offsetof(State,error),offsetof(State,position),offsetof(State,active),offsetof(State,rope)})p.push_back(at(off));return p;
 }
};
#endif
int main(int argc,char**argv){try{
 require(argc==3,"--cpu-test|--coordinator-admitted-device-window INPUTS");
 const std::string mode=argv[1];auto inputs=read_inputs(argv[2]);std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 std::vector<uint8_t>all;std::cout<<"{\"kind\":\"process\",\"pid\":"<<getpid()<<",\"cases\":2048,\"input_sha256\":\""<<digest(inputs.data(),sizeof inputs)<<"\"}\n"<<std::flush;
#ifdef OWN_RT_HOST_ONLY
 require(mode=="--cpu-test","CPU only");
 for(unsigned n=0;n<2048;++n){auto c=make_case(inputs,n);State a,b;a.active=b.active=c.active;a.error=b.error=c.error;
  auto pa=a.args(c.input(),c.type(),c.no),pb=b.args(c.input(),c.type(),c.no);
  if(n%2){p112route::host(pb);p78route::host(pa);}else{p78route::host(pa);p112route::host(pb);}
  compare(a,b,n);auto bytes=output_bytes(b);all.insert(all.end(),bytes.begin(),bytes.end());
  std::cout<<"{\"kind\":\"correctness\",\"case\":"<<n<<",\"exact\":true,\"nonfinite\":"<<(c.nonfinite?"true":"false")<<",\"sha256\":\""<<digest(bytes.data(),bytes.size())<<"\"}\n";
 }
#else
 require(mode=="--coordinator-admitted-device-window","coordinator admission required");
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});
 {DeviceState a(q),b(q);
 auto launch=[&](bool candidate,Case&c){State state;auto spec=state.spec(c.type(),c.no);auto bindings=(candidate?b:a).bindings(c.no);
  if(candidate){p112route::Kernel k;k.spec=spec;return k.submit(q,bindings,{});}
  p78route::Kernel k;k.spec=spec;return k.submit(q,bindings,{});
 };
 for(unsigned n=0;n<2048;++n){guard();auto c=make_case(inputs,n);State initial;initial.active=c.active;initial.error=c.error;a.upload(initial,c);b.upload(initial,c);
  if(n%2){launch(true,c).wait_and_throw();launch(false,c).wait_and_throw();}else{launch(false,c).wait_and_throw();launch(true,c).wait_and_throw();}
  auto expected=a.read(),actual=b.read();compare(expected,actual,n,c.nonfinite);
  // Failed/inactive rows must leave all public outputs and guards untouched.
  if(c.nonfinite){initial.error=1;compare(initial,actual,n,true);}
  else if(!c.active||c.error)compare(initial,actual,n);
  auto bytes=output_bytes(actual);all.insert(all.end(),bytes.begin(),bytes.end());
  std::cout<<"{\"kind\":\"correctness\",\"case\":"<<n<<",\"exact\":true,\"nonfinite\":"<<(c.nonfinite?"true":"false")<<",\"sha256\":\""<<digest(bytes.data(),bytes.size())<<"\"}\n";
 }
 // Warm-ups compile kernels only; timings use all 16 unchanged harness rows,
 // no nonfinite fast-reject samples. AB/BA order flips every repetition.
 for(unsigned row=0;row<16;++row){Case c;c.x=inputs[row];c.bf16=true;c.no=4;State initial;
  for(unsigned j=0;j<512;++j)c.xb[j]=iq3::bf16_bits(c.x[j]);
  a.upload(initial,c);b.upload(initial,c);
  for(unsigned rep=0;rep<72;++rep){guard();for(unsigned pos=0;pos<2;++pos){bool candidate=(pos^(rep&1))!=0;
    auto start=std::chrono::steady_clock::now();auto event=launch(candidate,c);event.wait_and_throw();
    uint64_t begin=event.get_profiling_info<sycl::info::event_profiling::command_start>(),end=event.get_profiling_info<sycl::info::event_profiling::command_end>();
    require(end>begin,"valid event timestamps");
    double wall=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count();
    if(rep>=8)std::cout<<"{\"kind\":\"sample\",\"row\":"<<row<<",\"repeat\":"<<rep-8<<",\"position\":"<<pos<<",\"view\":\""<<(candidate?"p112":"production")<<"\",\"start_ns\":"<<begin<<",\"end_ns\":"<<end<<",\"event_ns\":"<<end-begin<<",\"wall_ns\":"<<std::setprecision(17)<<wall<<"}\n";
   }compare(a.read(),b.read(),row);}
 }q.wait_and_throw();guard();
 }
#endif
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"cases\":2048,\"nonfinite_cases\":512,\"output_sha256\":\""<<digest(all.data(),all.size())<<"\"}\n"<<std::flush;return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
