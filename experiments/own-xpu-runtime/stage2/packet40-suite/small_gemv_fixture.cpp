#include "p30_submit.hpp"
#include "small_gemv_fixture.hpp"
#include "small_gemv.hpp"
#include "fixture_validation.hpp"
#include "k2_failure.hpp"
#include "failure.hpp"
#include <fstream>
#include <cstring>
namespace {
using namespace ownrt;using namespace integrated;
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "CPU compile-time sibling GEMV fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}void release(void* p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{if(!fixture_validation::only)std::memcpy(a,b,n);return next_handle();}Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void*const> p,std::span<const Event>)override{if(!fixture_validation::only)dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;unsigned serial=0;uint64_t maximum=0;
 static std::unique_ptr<Backend> backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit Runner(unsigned card):device(backend(card)),copy(device){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("small-gemv-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){if(!device.wait(e,std::chrono::seconds(300)))throw std::runtime_error("small GEMV bounded submission timeout");auto t=device.timing(e);if(t.end_ns>t.start_ns)maximum=std::max(maximum,t.end_ns-t.start_ns);}
 Allocation upload(const void* src,size_t n){auto h=alloc(std::min(n,size_t(4*1024*1024)),Memory::pinned),d=alloc(n);for(size_t off=0;off<n;off+=4*1024*1024){auto bytes=std::min(n-off,size_t(4*1024*1024));if(!fixture_validation::only)std::memcpy(device.arena.row(h).pointer,static_cast<const uint8_t*>(src)+off,bytes);finish(copy.copy(d,off,h,0,bytes,{}));}return d;}
 void clear(){device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();}
};
uint32_t random_word(uint32_t& state){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
std::vector<uint8_t> seed(const packet27::small::Shape& shape,unsigned mode,unsigned salt){
 auto fmt=iq3::layout(shape.type);size_t rb=shape.columns/fmt.elements*fmt.bytes;
 std::vector<uint8_t> packed(4*rb);uint32_t state=0x49ab3291u+salt;
 for(auto& byte:packed)byte=random_word(state);
 if(shape.type==iq3::Type::F32){for(size_t i=0;i<packed.size()/4;++i){float v=float(int(random_word(state)%127)-63)/1024.f;if(mode==1)v=i%2?-0.f:0.f;if(mode==2)v=iq3::bits_float(i%2?1:0x80000001);std::memcpy(packed.data()+i*4,&v,4);}}
 else for(size_t off=0;off<packed.size();off+=fmt.bytes){uint16_t half=mode==1?uint16_t((off/fmt.bytes)%2?0x8000:0):mode==2?uint16_t(1+(off/fmt.bytes)%1023):uint16_t(0x2000+random_word(state)%0x800);size_t at=off+(shape.type==iq3::Type::Q6_K?208:0);packed[at]=half&255;packed[at+1]=half>>8;}
 return arithmetic::is_expanded(shape.variant)?iq3::expanded::expand(shape.type,packed.data(),packed.size(),shape.columns):packed;
}
std::string klass(const std::string& name){return name.starts_with("small.ffn.")?"fusion:small.ffn":"fusion:"+name;}
AdapterFixtureReceipt gate(unsigned card,const std::filesystem::path& out,bool timing){
#ifdef OWN_RT_HOST_ONLY
 if(timing&&!fixture_validation::only)throw std::runtime_error("small GEMV timing requires coordinator device window");
#endif
 auto runner=std::make_unique<Runner>(card);unsigned checks=0;try{
  std::ofstream events(out/"events.jsonl",std::ios::app),bytes;if(!timing)bytes.open(out/"output.bin",std::ios::binary|std::ios::app);
  for(const auto& name:packet27::small::names()){
   if(timing&&name.starts_with("small.mini."))continue;
   const auto shape=packet27::small::shapes(name);
   for(unsigned mode=0;mode<(timing?1u:4u);++mode){auto& r=*runner;std::vector<Matrix> matrices;std::vector<unsigned> variants;std::vector<std::vector<uint16_t>> expected;std::vector<Allocation> hosts;
    std::vector<uint16_t> x(shape[0].columns);for(size_t i=0;i<x.size();++i){x[i]=iq3::bf16_bits(float(int(i*23%101)-50)/64.f);if(mode==1)x[i]=i%2?0x8000:0;if(mode==2)x[i]=i%2?1:0x8001;if(mode==3){constexpr uint16_t e[]{0x4f00,0xcf00,0x3000,0xb000,0x3f80,0xbf80};x[i]=e[i%6];}}
    auto xid=r.upload(x.data(),x.size()*2);
    for(size_t j=0;j<shape.size();++j){const auto& s=shape[j];auto four=seed(s,mode,j);auto rb=arithmetic::row_bytes(s.type,s.columns,s.variant);std::vector<uint8_t> weights(size_t(s.rows)*rb);for(size_t row=0;row<s.rows;++row)std::memcpy(weights.data()+row*rb,four.data()+(row%4)*rb,rb);
     Matrix m{};m.type=s.type;m.rows=s.rows;m.columns=s.columns;m.span=s.rows;m.w=r.upload(weights.data(),weights.size());m.x=xid;m.y=r.alloc(size_t(s.rows)*2);m.workspace=r.alloc(size_t(s.rows)*16);matrices.push_back(m);variants.push_back(s.variant);hosts.push_back(r.alloc(size_t(s.rows)*2,Memory::pinned));
     uint16_t cache[4]{};if(!fixture_validation::only)for(unsigned row=0;row<4;++row)cache[row]=iq3::bf16_bits(arithmetic::row(s.type,four.data()+row*rb,x.data(),s.columns,s.variant));std::vector<uint16_t> oracle(s.rows);for(unsigned row=0;row<s.rows;++row)oracle[row]=cache[row%4];expected.push_back(std::move(oracle));
    }
    // Arguments of every concrete tuple are validated on the host as well.
    packet27::small::validate(r.device,name,matrices,variants);
    auto reject=[&](auto mutation){auto bad=matrices;auto badv=variants;mutation(bad,badv);bool rejected=false;try{packet27::small::validate(r.device,name,bad,badv);}catch(const std::invalid_argument&){rejected=true;}if(!rejected)throw std::runtime_error("small GEMV malformed tuple accepted");++checks;};
    reject([](auto& m,auto&){m[0].rows++;});reject([](auto& m,auto&){m[0].columns++;});reject([](auto& m,auto&){m[0].routes=m[0].x;});reject([](auto& m,auto&){m[1].y=m[0].x;});reject([](auto&,auto& v){v[0]^=1;});
    for(const std::string candidate:(name=="small.hc"||name=="small.ffn.q6"||name=="small.ffn.q8")?std::vector<std::string>{"round2","p30.small.rows4"}:std::vector<std::string>{"round2"}){
    bool excluded[2]{};
    for(unsigned repetition=0;repetition<(timing&&!fixture_validation::only?200u:1u);++repetition)for(unsigned variant=0;variant<2;++variant){if(excluded[variant])continue;try{
     fixture_validation::inject_failure(klass(name),variant);std::vector<Event> submitted;
     if(variant){auto launch=candidate=="p30.small.rows4"?p30integrated::small(r.device,name,matrices,variants):packet27::small::submit(r.device,name,matrices,variants);submitted.push_back(launch.last);r.finish(launch.last);}
     else for(size_t i=0;i<matrices.size();++i){auto launch=dense(r.device,matrices[i],variants[i]);for(Event e=launch.first;e<=launch.last;++e)submitted.push_back(e);}
     if(!variant)r.finish(submitted.back());
     std::vector<std::pair<Event,EventTiming>> times;for(auto e:submitted)times.emplace_back(e,r.device.timing(e));
     if(!timing||fixture_validation::only||repetition==0||repetition==199)for(size_t i=0;i<matrices.size();++i){auto n=expected[i].size()*2;r.finish(r.copy.copy(hosts[i],0,matrices[i].y,0,n,{}));auto actual=r.device.arena.row(hosts[i]).pointer;
      if(!fixture_validation::only&&std::memcmp(actual,expected[i].data(),n))throw std::runtime_error(name+" sibling byte mismatch member "+std::to_string(i)+" mode "+std::to_string(mode)+" implementation "+std::to_string(variant));
      if(!timing&&!fixture_validation::only)bytes.write(static_cast<const char*>(actual),n);
     }
     for(auto [e,t]:times)if(timing)events<<"{\"class\":"<<quote(klass(name))<<",\"workload\":"<<quote(name)<<",\"variant\":\""<<(variant?"specialised":"packet18")<<"\",\"candidate\":"<<quote(candidate)<<",\"implementation\":"<<quote(variant?candidate:"r5.sum.members")<<",\"candidate_available\":true,\"same_kernel\":false,\"repetition\":"<<repetition<<",\"event\":"<<e<<",\"stage_count\":"<<times.size()<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true,\"bytes_equal\":true}\n";
     if(fixture_validation::only)std::ofstream(out/"validation-entries.jsonl",std::ios::app)<<"{\"class\":"<<quote(klass(name))<<",\"workload\":"<<quote(name)<<",\"candidate\":"<<quote(variant?(candidate=="round2"?name:candidate):"r5.sum.members")<<",\"mode\":"<<mode<<"}\n";
     r.device.retire_completed_events();++checks;
    }catch(const std::exception& e){if(!timing||(fixture_validation::only&&!dynamic_cast<const fixture_validation::InjectedFailure*>(&e)))throw;packet26::candidate_failure(out,klass(name),variant?"specialised":"packet18",name,e,variant?candidate:"r5.sum.members");excluded[variant]=true;r.device.retire_completed_events();}}
    }
    r.clear();
   }
  }
  auto receipt=runner->device.shutdown(std::chrono::seconds(60));if(!receipt.safe_to_exit||receipt.exit_code)throw std::runtime_error("small GEMV fixture teardown");return {checks,runner->maximum,receipt.json()};
 }catch(const std::exception& e){std::ofstream(out/"small-gemv-failure.json")<<"{\"passed\":false,\"error\":"<<quote(e.what())<<"}\n";packet26::failure(runner->device,out,e.what());throw;}
}
}
AdapterFixtureReceipt small_gemv_fixture_gate(unsigned card,const std::filesystem::path& out){return gate(card,out,false);}
AdapterFixtureReceipt small_gemv_timing_gate(unsigned card,const std::filesystem::path& out){return gate(card,out,true);}
