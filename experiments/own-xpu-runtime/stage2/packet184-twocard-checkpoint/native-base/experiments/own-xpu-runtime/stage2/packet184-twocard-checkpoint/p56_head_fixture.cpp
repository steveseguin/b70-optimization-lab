#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p56_head_fixture.cpp"
// Standalone synthetic head window. No model payload is opened.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/p56_prefix.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/p33_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/round2_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/failure.hpp"
#include <array>
#include <cstring>
#include <csignal>
#include <fstream>
#include <iostream>
#include <vector>
using namespace ownrt;
using namespace integrated;
namespace {
volatile std::sig_atomic_t stopping=0;
void stop(int){stopping=1;}
void need(bool b,const char* m){if(!b)throw std::runtime_error(m);}
#ifndef OWN_RT_HOST_ONLY
struct Run {
 Device device;CopyEngine copy;std::vector<Allocation> owned;unsigned serial=0;
 explicit Run():device(make_sycl_device(0,true)),copy(device){}
 Allocation alloc(size_t n,Memory kind=Memory::device){auto a=device.arena.allocate("p56-head-"+std::to_string(serial++),n,kind,Category::scratch,Lifetime::transaction);owned.push_back(a);return a;}
 void wait(Event e){need(device.wait(e,std::chrono::seconds(60)),"head event deadline");}
 void upload(Allocation dst,const void* p,size_t n,Allocation staging,size_t off=0){need(!stopping,"coordinator stop requested");std::memcpy(device.arena.row(staging).pointer,p,n);wait(copy.copy(dst,off,staging,0,n,{}));}
 void read(Allocation src,void* p,size_t n,Allocation staging){wait(copy.copy(staging,0,src,0,n,{}));std::memcpy(p,device.arena.row(staging).pointer,n);}
 double elapsed(Launch l){wait(l.last);double us=0;for(auto e=l.first;e<=l.last;++e){auto t=device.timing(e);need(t.end_ns>t.start_ns,"missing GPU event timing");us+=double(t.end_ns-t.start_ns)/1000.;}return us;}
};
#endif
}
int main(int argc,char**argv){
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 std::filesystem::path out;bool authorized=false;unsigned iterations=100;int card=-1;
#ifndef OWN_RT_HOST_ONLY
 std::unique_ptr<Run> run;
#endif
 try {
  for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--output"&&i+1<argc)out=argv[++i];else if(k=="--card"&&i+1<argc)card=std::stoi(argv[++i]);else if(k=="--iterations"&&i+1<argc)iterations=std::stoul(argv[++i]);else if(k=="--authorized-device-window")authorized=true;else if(k=="--stop-fd"&&i+1<argc)set_stop_channel(std::stoi(argv[++i]));else throw std::invalid_argument("p56 head arguments");}
  need(authorized&&card==0&&iterations==100&&!out.empty(),"sealed card0 100-iteration coordinator window required");
#ifdef OWN_RT_HOST_ONLY
  throw std::invalid_argument("host binary refuses GPU timing; use p56_cpu_gate.py for CPU evidence");
#else
  std::filesystem::create_directories(out);std::ofstream events(out/"events.jsonl"),comparisons(out/"comparisons.jsonl");need(bool(events)&&bool(comparisons),"output files");
  run=std::make_unique<Run>();auto&r=*run;constexpr unsigned columns=2560;const auto stride=arithmetic::row_bytes(iq3::Type::Q6_K,columns,6);
  const unsigned full=p56::full_rows;std::vector<uint8_t>tile(256*stride);uint32_t seed=0x56;
  for(auto&v:tile){seed=seed*1664525u+1013904223u;v=seed>>24;}
  for(unsigned row=0;row<256;++row)for(unsigned j=0;j<columns/16;++j){float scale=0.00390625f*float(1+(row+j)%4);std::memcpy(tile.data()+row*stride+columns+j*4,&scale,4);}
  auto staging=r.alloc(std::max(tile.size(),size_t(full)*2),Memory::pinned);Matrix m{};m.type=iq3::Type::Q6_K;m.rows=full;m.columns=columns;m.span=full;m.w=r.alloc(size_t(full)*stride);m.x=r.alloc(columns*2);m.y=r.alloc(full*2);m.workspace=r.alloc(size_t(full)*32);
  for(unsigned row=0;row<full;row+=256)r.upload(m.w,tile.data(),std::min(256u,full-row)*stride,staging,size_t(row)*stride);
  Spec s{};s.op=Op::argmax;s.implementation=2;s.ni=s.no=1;s.sizes[0]=full;s.sizes[1]=1;s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
  auto token=r.alloc(4),scratch=r.alloc(size_t(full)*4),error=r.alloc(4),position=r.alloc(4),active=r.alloc(4),rope=r.alloc(4);uint32_t zero=0,one=1;r.upload(error,&zero,4,staging);r.upload(position,&zero,4,staging);r.upload(active,&one,4,staging);r.upload(rope,&zero,4,staging);
  std::array<Allocation,7> bindings{m.y,token,scratch,error,position,active,rope};std::vector<uint16_t>x(columns),reference(full),actual(full);unsigned checks=0;
  const std::array<unsigned,5> rows{32768,65536,98304,p56::prefix_rows,full};
  // Every measured iteration changes hidden inputs. All candidates read one shared
  // full head allocation; no per-prefix weight copies or precomputed logits.
  for(unsigned iteration=0;iteration<iterations+8;++iteration){
   for(unsigned j=0;j<columns;++j)x[j]=iq3::bf16_bits(float(int((j*17+iteration*7)%127)-63)/128.f);r.upload(m.x,x.data(),x.size()*2,staging);
   r.wait(p33::submit(r.device,{m},"p33.dense.segment",false,6).last);r.read(m.y,reference.data(),reference.size()*2,staging);
   for(unsigned arm=0;arm<rows.size();++arm){need(!stopping,"coordinator stop requested");auto n=rows[(arm+iteration)%rows.size()];auto mm=m;p56::restrict_matrix(mm,n);auto ss=s;p56::restrict_argmax(ss,n);
    const auto head_us=r.elapsed(p33::submit(r.device,{mm},"p33.dense.segment",false,6));const auto argmax_us=r.elapsed(round2::submit_simple(r.device,ss,bindings,{}));
    // Untimed readback checks every prefix logit, and argmax lower-ID ties.
    r.read(m.y,actual.data(),n*2,staging);need(!std::memcmp(actual.data(),reference.data(),n*2),"prefix logits differ from full head");int expected=0;for(unsigned j=1;j<n;++j)if(iq3::bits_float(uint32_t(reference[j])<<16)>iq3::bits_float(uint32_t(reference[expected])<<16))expected=int(j);int observed=-1;r.read(token,&observed,4,staging);r.read(error,&zero,4,staging);need(!zero&&observed==expected,"prefix proposal or finite gate differs");++checks;
    comparisons<<"{\"iteration\":"<<iteration<<",\"rows\":"<<n<<",\"bytes_equal\":true,\"argmax_equal\":true,\"argmax\":"<<observed<<",\"prefix_sha256\":"<<quote(packet26::hash(actual.data(),n*2))<<"}\n";
    if(iteration>=8)events<<"{\"iteration\":"<<iteration-8<<",\"rows\":"<<n<<",\"head_us\":"<<head_us<<",\"argmax_us\":"<<argmax_us<<",\"total_us\":"<<head_us+argmax_us<<",\"bytes_equal\":true,\"argmax_equal\":true}\n";
    r.device.retire_completed_events();
   }
  }
  r.device.retire_completed_events();for(auto a:r.owned)r.device.arena.release(a);auto exit=r.device.shutdown(std::chrono::seconds(60));need(exit.safe_to_exit&&!exit.exit_code,"head window teardown failed");
  std::ofstream(out/"receipt.json")<<"{\"schema\":\"packet56.head-fixture.v1\",\"passed\":true,\"device_executed\":true,\"card\":0,\"iterations\":100,\"checks\":"<<checks<<",\"full_rows\":"<<full<<",\"chosen_rows\":"<<p56::prefix_rows<<",\"head_bytes\":"<<size_t(full)*stride<<",\"weight_copies\":1,\"teardown\":"<<exit.json()<<"}\n";return 0;
#endif
 }catch(const std::exception&e){
#ifndef OWN_RT_HOST_ONLY
  if(run)packet26::failure(run->device,out,e.what());
#endif
  std::cerr<<e.what()<<'\n';return 1;
 }
}
