#define integrated kernel_fixture_snapshot_integrated
#define ng kernel_fixture_snapshot_ng
#define detmath kernel_fixture_snapshot_detmath
#define rope_constants kernel_fixture_snapshot_rope_constants
#include "prototype/snapshot/reference.hpp"
#undef integrated
#undef ng
#undef detmath
#undef rope_constants
#include "kernels_v2.hpp"
#include "kernels_fixture.hpp"
#include "failure.hpp"
#include "owner.hpp"
#include "runtime_kernels.hpp"
#include <fstream>
#include <random>
#include <cstring>
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace {
using namespace ownrt;
#ifdef OWN_RT_HOST_ONLY
using integrated::HostOperation;
#endif
namespace ref=kernel_fixture_snapshot_ng;
void check(bool x,const std::string& text){if(!x)throw std::runtime_error(text);}
struct Fixture {
 ng::Shape shape;std::array<std::vector<uint8_t>,19> data;std::array<bool,19> outputs{};
 std::string name;
 static std::vector<uint8_t> integer(int32_t n){std::vector<uint8_t> b(4);std::memcpy(b.data(),&n,4);return b;}
 void rope(){std::ifstream in(std::filesystem::path(__FILE__).parent_path()/"rope.bf16",std::ios::binary);data[16].assign(std::istreambuf_iterator<char>(in),{});check(data[16].size()==rope_constants::bytes,"kernel fixture RoPE");}
 explicit Fixture(const std::filesystem::path& path):name(path.filename().string()){
  std::ifstream in(path,std::ios::binary);in.read(reinterpret_cast<char*>(&shape),sizeof shape);ng::validate(shape);
  for(int slot=0;slot<16;++slot){uint32_t n=0,o=0;in.read(reinterpret_cast<char*>(&n),4);in.read(reinterpret_cast<char*>(&o),4);check(n&&n<=128*1024*1024,"kernel fixture size");data[slot].resize(n);outputs[slot]=o;in.read(reinterpret_cast<char*>(data[slot].data()),n);if(o)in.seekg(n,std::ios::cur);}
  check(bool(in)&&in.peek()==EOF,"kernel fixture bytes");int32_t control[3];check(data[15].size()>=12,"kernel fixture control");std::memcpy(control,data[15].data(),12);
  data[15]=integer(control[2]);data[17]=integer(control[0]);data[18]=integer(control[1]);outputs[15]=true;rope();
 }
 Fixture(ng::Shape s,std::string label):shape(s),name(std::move(label)){
  auto sizes=ng::required_bytes(s);for(int slot=0;slot<19;++slot)data[slot].resize(std::max(size_t(4),sizes[slot]));
  data[15]=integer(0);data[17]=integer(0);data[18]=integer(1);rope();
  for(int slot=0;slot<15;++slot)for(size_t j=0;j<data[slot].size()/2;++j){uint16_t v=ng::Args::bits(float(int((j*17+slot*11)%71)-35)*0.03125f);std::memcpy(data[slot].data()+j*2,&v,2);}
  outputs[s.op==ng::norm?2:5]=true;if(s.op==ng::combine_norm)outputs[4]=true;outputs[15]=true;
 }
 ng::Args args(){ng::Args a;for(int j=0;j<19;++j)a.p[j]=data[j].data();return a;}
 void reference(){ref::Shape s;static_assert(sizeof(s)==sizeof(shape));std::memcpy(&s,&shape,sizeof s);ref::Args a;for(int j=0;j<15;++j)a.p[j]=data[j].data();int32_t control[]{0,0,0};std::memcpy(control,data[17].data(),4);std::memcpy(control+1,data[18].data(),4);std::memcpy(control+2,data[15].data(),4);a.p[15]=control;ref::reference::cpu(s,a);std::memcpy(data[15].data(),control+2,4);}
};
#ifdef OWN_RT_HOST_ONLY
struct Cpu:Backend {
 std::string identity()const override{return "CPU packet24 kernel fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}
 void release(void* p,Memory)override{::operator delete(p);}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void* const> p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
struct Kernel:HostOperation {
 ng::Shape shape;bool v2;int stage;
 void run(std::span<void* const> p)const override{ng::Args a;for(int j=0;j<19;++j)a.p[j]=p[j];auto* scratch=static_cast<float*>(p[19]);
  if(v2)for(size_t i=0;i<ng2::work_items(shape,stage);++i)ng2::body(shape,a,stage,i,scratch,ng2::HostGuard{});
  else ng::cpu(shape,a);
 }
};
#else
struct Guard {
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
};
struct Team:Guard {
 sycl::nd_item<1> item;float* x;
 template<class F>void each(int n,F f)const{for(int j=item.get_local_linear_id();j<n;j+=128)f(j);}
 void barrier()const{item.barrier(sycl::access::fence_space::global_and_local);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int k=j*2*stride;x[base+k]=x[base+k]+(k+stride<n?x[base+k+stride]:0.f);});barrier();}return x[base];}
};
struct Kernel:SyclOperation {
 ng::Shape shape;bool v2;int stage;
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override{
  ng::Args a;for(int j=0;j<19;++j)a.p[j]=p[j];auto s=shape;int st=stage;float* scratch=static_cast<float*>(p[19]);
  if(v2){size_t count=ng2::work_items(s,st);return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(count),[=](sycl::id<1> id){ng2::body(s,a,st,id[0],scratch,Guard{});});});}
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> local(ng::local_floats(s),h);h.parallel_for(sycl::nd_range<1>(ng::groups(s)*128,128),[=](sycl::nd_item<1> it){Team team{{},it,local.get_multi_ptr<sycl::access::decorated::no>().get()};ng::group(s,a,it.get_group_linear_id(),team);});});
 }
};
#endif
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;size_t serial=0;uint64_t maximum=0;
 static std::unique_ptr<Backend> backend(unsigned card){
 #ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
 #else
 return make_sycl_device(card,true);
 #endif
 }
 explicit Runner(unsigned card):device(backend(card)),copy(device){}
 Allocation allocate(size_t n,Memory m=Memory::device){auto a=device.arena.allocate("kernel-fixture-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(a);return a;}
 void finish(Event e){check(device.wait(e,std::chrono::seconds(300)),"kernel fixture submission deadline");auto t=device.timing(e);maximum=std::max(maximum,t.end_ns-t.start_ns);}
 Allocation upload(const std::vector<uint8_t>& b){auto host=allocate(b.size(),Memory::pinned),out=allocate(b.size());std::memcpy(device.arena.row(host).pointer,b.data(),b.size());finish(copy.copy(out,0,host,0,b.size(),{}));return out;}
 void run(Fixture& fixture,bool v2){std::vector<Allocation> bindings;for(auto& b:fixture.data)bindings.push_back(upload(b));auto shapes=std::vector<ng::Shape>{fixture.shape};if(fixture.shape.op==ng::attention_score){auto s=fixture.shape;s.op=ng::attention_softmax;shapes.push_back(s);s.op=ng::attention_value;shapes.push_back(s);}
  size_t floats=1;for(auto s:shapes)if(ng2::supported(s))floats=std::max(floats,ng2::scratch_floats(s));bindings.push_back(allocate(floats*4));
  for(auto s:shapes)for(int st=0;st<(v2&&ng2::supported(s)?ng2::stages(s):1);++st){Kernel op;op.shape=s;op.v2=v2&&ng2::supported(s);op.stage=st;finish(device.compute(op,bindings,{}));}
  for(int j=0;j<19;++j)if(fixture.outputs[j]){auto host=allocate(fixture.data[j].size(),Memory::pinned);finish(copy.copy(host,0,bindings[j],0,fixture.data[j].size(),{}));std::memcpy(fixture.data[j].data(),device.arena.row(host).pointer,fixture.data[j].size());}
  device.retire_completed_events();for(auto a:owned)device.arena.release(a);owned.clear();
 }
};
void compare(const Fixture& reference,const Fixture& candidate,const std::filesystem::path& output,std::ofstream& bytes,const char* variant){
 for(int j=0;j<19;++j)if(reference.outputs[j]){bool equal=reference.data[j]==candidate.data[j];std::string label="packet24 "+reference.name+" "+variant+" slot="+std::to_string(j);packet23::row(output,label,candidate.data[j].data(),candidate.data[j].size(),equal);check(equal,label);bytes.write(reinterpret_cast<const char*>(candidate.data[j].data()),candidate.data[j].size());}
}
}
unsigned kernel_fixture_gate(unsigned card,const std::filesystem::path& output,unsigned seed){
 std::filesystem::create_directories(output);auto dir=std::filesystem::path(__FILE__).parent_path()/"build/fusion-fixtures";
 std::ifstream list(dir/"cases.txt");check(bool(list),"packet24 fixture list missing");std::vector<Fixture> fixtures;std::string name;
 while(list>>name){Fixture f(dir/name);fixtures.push_back(std::move(f));}
 unsigned inherited=fixtures.size();check(inherited==72,"packet24 requires all72 inherited fixtures");
 for(int n:{1,3,17,255,2560})for(int op:{int(ng::norm),int(ng::combine_norm)})for(int unit:{0,1}){ng::Shape s;s.op=op;s.width=n;s.tokens=1;s.heads=4;s.flags=unit;fixtures.emplace_back(s,"odd-width-"+std::to_string(n)+"-op-"+std::to_string(op)+"-unit-"+std::to_string(unit));}
 std::mt19937 rng(seed);std::shuffle(fixtures.begin(),fixtures.end(),rng);Runner runner(card);std::ofstream bytes(output/"kernel-output.bin",std::ios::binary);unsigned checked=0;
 try {for(const auto& source:fixtures){auto reference=source,v1=source,v2=source;reference.reference();runner.run(v1,false);runner.run(v2,true);compare(reference,v1,output,bytes,"core/v1");compare(reference,v2,output,bytes,"core/v2");compare(v1,v2,output,bytes,"v1/v2");++checked;}
  auto shutdown=runner.device.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"packet24 fixture teardown");
  std::ofstream receipt(output/"kernel-fixture.json");receipt<<"{\"schema\":\"own-runtime.packet24.kernel-fixtures.v1\",\"passed\":true,\"seed\":"<<seed<<",\"fixtures\":"<<checked<<",\"inherited\":"<<inherited<<",\"odd_width_cases\":20,\"pairwise_checks\":"<<checked*3<<",\"max_submission_ns\":"<<runner.maximum<<",\"device_executed\":";
 #ifdef OWN_RT_HOST_ONLY
 receipt<<"false";
 #else
 receipt<<"true";
 #endif
 receipt<<",\"teardown\":"<<shutdown.json()<<"}\n";return checked;
 }catch(const std::exception& e){packet23::failure(runner.device,output,e.what());throw;}
}
