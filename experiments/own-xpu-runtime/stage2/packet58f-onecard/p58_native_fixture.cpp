// Actual production submission ABI. Every selectable path is exercised regardless
// of selection.json; the device coordinator separately gates captured full-model use.
#include "p49d_submit.hpp"
#include "p49c_submit.hpp"
#include "p49b_expert_submit.hpp"
#include "p30_submit.hpp"
#include "adapter.hpp"
#include "rope.hpp"
#include "failure.hpp"
#include <array>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <vector>
namespace {
using namespace ownrt;using namespace integrated;
void check(bool v,const std::string&s){if(!v)throw std::runtime_error(s);}
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "CPU packet49d actual submitters";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void*p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void*a,const void*b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation&op,std::span<void*const>p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner {
 Device d;CopyEngine copy;std::vector<Allocation>owned;size_t serial=0;std::chrono::steady_clock::time_point deadline;
 static std::unique_ptr<Backend>backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit Runner(unsigned card,unsigned seconds):d(backend(card)),copy(d),deadline(std::chrono::steady_clock::now()+std::chrono::seconds(seconds)){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=d.arena.allocate("p49d-fixture-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){auto left=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-std::chrono::steady_clock::now());check(left.count()>0,"fixture total deadline");check(d.wait(e,std::min(left,std::chrono::milliseconds(300000))),"fixture submission timeout");}
 void write(Allocation id,const void*p,size_t n){auto h=alloc(n,Memory::pinned);std::memcpy(d.arena.row(h).pointer,p,n);finish(copy.copy(id,0,h,0,n,{}));d.arena.release(h);owned.pop_back();}
 Allocation upload(const void*p,size_t n){auto id=alloc(n);write(id,p,n);return id;}
 template<class T>Allocation vec(const std::vector<T>&v){return upload(v.data(),v.size()*sizeof(T));}
 Allocation word(uint32_t v){return upload(&v,4);}
 std::vector<uint8_t>read(Allocation id){size_t n=d.arena.row(id).bytes;auto h=alloc(n,Memory::pinned);finish(copy.copy(h,0,id,0,n,{}));auto p=static_cast<uint8_t*>(d.arena.row(h).pointer);std::vector<uint8_t>v(p,p+n);d.arena.release(h);owned.pop_back();return v;}
 using Snap=std::vector<std::vector<uint8_t>>;
 Snap snapshot(const std::vector<Allocation>&ids){Snap out;for(auto id:ids)out.push_back(read(id));return out;}
 void restore(const std::vector<Allocation>&ids,const Snap&v){for(size_t j=0;j<ids.size();++j)write(ids[j],v[j].data(),v[j].size());}
 void clear(){d.retire_completed_events();for(auto id:owned)d.arena.release(id);owned.clear();}
};
std::vector<uint16_t>activation(size_t n,unsigned scenario,unsigned row){std::vector<uint16_t>v(n);for(size_t i=0;i<n;++i)v[i]=iq3::bf16_bits(float(int((i*37+row*73)%257)-128)/512.f);if(scenario==6)v[0]=0x7fc1;if(scenario==7){v[0]=0x7f80;v[8]=0xff80;}if(scenario==8){v[0]=0x0001;v[1]=0x8001;v[2]=0x8000;}return v;}

}
#include "p49d_expert.hpp"
#include "p58_pointer.hpp"
#include <csignal>
namespace {
static volatile std::sig_atomic_t p58_stopping=0;
static void p58_stop(int){p58_stopping=1;}
struct Times {double host=0,vram=0,streamed=0;size_t bytes=0,checks=0,working_set=0;std::string digest;};
std::vector<uint8_t> fixture_bank(iq3::Type t,unsigned k,unsigned rows,unsigned experts,unsigned seed,bool compact){
 auto f=iq3::layout(t);size_t raw_stride=k/f.elements*f.bytes,stride=compact?p49bgemv::layout(t,k).row_bytes:raw_stride;
 std::vector<uint8_t> bank(size_t(rows)*experts*stride),raw(raw_stride);uint32_t state=seed;
 for(unsigned row=0;row<rows*experts;++row){for(auto&v:raw){state=state*1664525+1013904223;v=state>>24;}
  for(unsigned block=0;block<k/f.elements;++block){uint16_t scale=uint16_t(0x1400+(row+block)%0x400);std::memcpy(raw.data()+block*f.bytes,&scale,2);}
  auto*dest=bank.data()+size_t(row)*stride;if(compact)p49bgemv::repack_row(t,k,raw.data(),dest);else std::memcpy(dest,raw.data(),stride);
 }return bank;
}
template<iq3::Type T,unsigned K,bool Gate>Times exercise(Runner&r,unsigned iterations,std::ofstream&detail){
 constexpr unsigned rows=Gate?640:2560,experts=10,count=10;constexpr auto kind=Gate?p39::Kind::expert_checks:p39::Kind::down_status;
 auto bank=fixture_bank(T,K,rows,experts,5801,T!=iq3::Type::IQ3_S),peer=Gate?fixture_bank(T,K,rows,experts,5802,T!=iq3::Type::IQ3_S):bank;
 const size_t expert_bytes=bank.size()/experts;Times times;times.bytes=bank.size()*(Gate?2:1);
 const size_t rotation=std::max(size_t(3*iterations+1),(size_t(128)*1024*1024+bank.size()-1)/bank.size());times.working_set=bank.size()*rotation*(Gate?2:1);
 auto w=r.vec(bank),u=Gate?r.vec(peer):w,h=r.alloc(bank.size()*rotation,Memory::pinned),hu=Gate?r.alloc(peer.size()*rotation,Memory::pinned):h;
 for(size_t j=0;j<rotation;++j){std::memcpy(static_cast<uint8_t*>(r.d.arena.row(h).pointer)+j*bank.size(),bank.data(),bank.size());if(Gate)std::memcpy(static_cast<uint8_t*>(r.d.arena.row(hu).pointer)+j*peer.size(),peer.data(),peer.size());}
 auto table=r.alloc(experts*sizeof(p58::Pointer)),up_table=Gate?r.alloc(experts*sizeof(p58::Pointer)):table;
 Matrix a{};a.type=T;a.w=w;a.rows=rows;a.columns=K;a.span=rows;a.count=count;a.experts=experts;
 a.x=r.vec(activation(K*(Gate?1:count),0,0));a.y=r.vec(std::vector<uint16_t>(rows*count,0));a.status=r.vec(std::vector<uint32_t>(count,0));a.workspace=r.alloc(rows*count*32);
 std::vector<iq3::Route> routes(count);for(unsigned j=0;j<count;++j)routes[j]={(j*7)%experts,0,rows};a.routes=r.vec(routes);auto b=a;b.w=u;if(Gate){b.y=r.vec(std::vector<uint16_t>(rows*count,0));b.status=r.vec(std::vector<uint32_t>(count,0));}
 p39::Bindings control;control.error=r.word(0);control.active=r.word(1);control.position=r.word(0);control.capacity=4096;
 auto invoke=[&](bool indirect){auto aa=a,bb=b;aa.w=indirect?table:w;bb.w=indirect?up_table:u;std::vector<Matrix>m{aa};if(Gate)m.push_back(bb);auto controls=control;controls.indirect=indirect;
  if constexpr(T==iq3::Type::IQ3_S)return p39::submit(r.d,m,kind,controls);else return p49d::expert(r.d,m,kind,controls);};
 std::vector<Allocation>outputs{a.y,a.status,control.error};if(Gate){outputs.push_back(b.y);outputs.push_back(b.status);}
 r.finish(invoke(false).last);auto expected=r.snapshot(outputs);std::vector<uint8_t> flattened;for(auto&v:expected)flattened.insert(flattened.end(),v.begin(),v.end());times.digest=packet26::hash(flattened.data(),flattened.size());
 for(unsigned mode=0;mode<4;++mode){check(!p58_stopping,"K1 cooperative stop");std::vector<p58::Pointer>pt(experts),ut(experts);
  for(unsigned id=0;id<experts;++id){bool host=mode==1||(mode==2&&id%2);pt[id]={uint64_t(r.d.arena.row(host?h:w).pointer)+id*expert_bytes,mode+1};ut[id]={uint64_t(r.d.arena.row(host?hu:u).pointer)+id*expert_bytes,mode+1};}
  r.write(table,pt.data(),pt.size()*sizeof(p58::Pointer));if(Gate)r.write(up_table,ut.data(),ut.size()*sizeof(p58::Pointer));
  if(mode==3){std::vector<uint8_t> poison(bank.size(),0x5a);r.write(w,poison.data(),poison.size());if(Gate)r.write(u,poison.data(),poison.size());
    r.finish(r.copy.copy(w,0,h,0,bank.size(),{}));if(Gate)r.finish(r.copy.copy(u,0,hu,0,peer.size(),{}));}
  r.finish(invoke(true).last);check(r.snapshot(outputs)==expected,"K1 pointer output differs from production");++times.checks;
  double elapsed=0;for(unsigned i=0;i<iterations;++i){check(!p58_stopping,"K1 cooperative stop");
   // Every timed host read has fresh physical addresses. Region0 was the
   // exactness/compile warmup; each mode has disjoint measured regions; no timed host address is reused.
   if(mode==1||mode==2){for(unsigned id=0;id<experts;++id){bool host=mode==1||id%2;size_t offset=host?size_t((mode-1)*iterations+i+1)*bank.size():0;
      pt[id]={uint64_t(r.d.arena.row(host?h:w).pointer)+offset+id*expert_bytes,mode+1};ut[id]={uint64_t(r.d.arena.row(host?hu:u).pointer)+offset+id*expert_bytes,mode+1};}
    r.write(table,pt.data(),pt.size()*sizeof(p58::Pointer));if(Gate)r.write(up_table,ut.data(),ut.size()*sizeof(p58::Pointer));}
   auto start=std::chrono::steady_clock::now();
   if(mode==3){r.finish(r.copy.copy(w,0,h,size_t((mode-1)*iterations+i+1)*bank.size(),bank.size(),{}));if(Gate)r.finish(r.copy.copy(u,0,hu,size_t(2*iterations+i+1)*peer.size(),peer.size(),{}));}
   auto run=invoke(true);r.finish(run.last);
#ifdef OWN_RT_HOST_ONLY
   elapsed+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
#else
   if(mode==3)elapsed+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
   else {auto timing=r.d.timing(run.last);elapsed+=double(timing.end_ns-timing.start_ns)/1e6;}
#endif
   r.d.retire_completed_events();
  }
  check(r.snapshot(outputs)==expected,"K1 timed output differs from production");++times.checks;
  elapsed/=iterations;if(mode==0)times.vram=elapsed;if(mode==1)times.host=elapsed;if(mode==3)times.streamed=elapsed;
  detail<<"{\"format\":"<<unsigned(T)<<",\"gate\":"<<(Gate?"true":"false")<<",\"mode\":"<<mode<<",\"ms\":"<<elapsed<<",\"bytes\":"<<times.bytes<<",\"working_set_bytes\":"<<times.working_set<<",\"cold_rotation\":true,\"byte_identical\":true}\n";detail.flush();
 }
 r.clear();return times;
}
}
int main(int argc,char**argv){std::filesystem::path out;unsigned card=0,iterations=20;bool authorized=false;std::unique_ptr<Runner>r;
 try{for(int i=1;i<argc;++i){std::string key=argv[i];auto value=[&](){check(i+1<argc,"missing argument");return std::string(argv[++i]);};if(key=="--output")out=value();else if(key=="--card")card=std::stoul(value());else if(key=="--iterations")iterations=std::stoul(value());else if(key=="--authorized-device-window")authorized=true;else if(key=="--stop-fd")ownrt::set_stop_channel(std::stoi(value()));else throw std::invalid_argument("K1 unknown option");}
 check(!out.empty()&&!std::filesystem::exists(out)&&iterations>0&&iterations<=20,"K1 bounds/output");
#ifdef OWN_RT_HOST_ONLY
 check(!authorized,"host cannot execute device window");
#else
 check(authorized,"device authorization required");
#endif
 std::filesystem::create_directories(out);std::signal(SIGTERM,p58_stop);std::signal(SIGINT,p58_stop);r=std::make_unique<Runner>(card,900);r->d.before_compute=[]{check(!p58_stopping,"K1 cooperative stop");};std::ofstream detail(out/"k1-cases.jsonl");
 auto a=exercise<iq3::Type::IQ2_S,2560,true>(*r,iterations,detail),b=exercise<iq3::Type::IQ3_S,2560,true>(*r,iterations,detail),c=exercise<iq3::Type::IQ4_NL,640,false>(*r,iterations,detail);
 auto shutdown=r->d.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"K1 teardown");
 std::ofstream receipt(out/"k1.json");receipt<<"{\"schema\":\"packet58.k1.v1\",\"passed\":true,\"safe_to_exit\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"zero_copy_supported\":true,\"zero_copy_bytes_equal\":true,\"mixed_bytes_equal\":true,\"streamed_bytes_equal\":true,\"host_ms\":"<<a.host+b.host+c.host<<",\"vram_ms\":"<<a.vram+b.vram+c.vram<<",\"streamed_ms\":"<<a.streamed+b.streamed+c.streamed<<",\"bytes_per_iteration\":"<<a.bytes+b.bytes+c.bytes<<",\"exact_output_sha256\":"<<quote(packet26::hash((a.digest+b.digest+c.digest).data(),(a.digest+b.digest+c.digest).size()))<<",\"working_set_bytes\":"<<std::max({a.working_set,b.working_set,c.working_set})<<",\"cold_rotation\":true,\"checks\":"<<a.checks+b.checks+c.checks<<",\"iterations\":"<<iterations<<",\"teardown\":"<<shutdown.json()<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';if(r)packet26::failure(r->d,out,e.what());return 1;}}
