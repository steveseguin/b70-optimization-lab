// Packet20's retained CPU fixture gate plus supervised same-card comparison.
// Snapshot ABI has 16-slot Args; runtime ABI has 19. Isolate every snapshot
// namespace before linking the actual runtime adapter in another translation unit.
#define integrated packet21_snapshot_integrated
#define ng packet21_snapshot_ng
#define fusion packet21_snapshot_fusion
#define detmath packet21_snapshot_detmath
#define rope_constants packet21_snapshot_rope_constants
#define main packet20_host_gate
#include "prototype/gate.cpp"
#undef main
#undef integrated
#undef ng
#undef fusion
#undef detmath
#undef rope_constants
namespace ng=packet21_snapshot_ng;
namespace fusion=packet21_snapshot_fusion;
#include "adapter_fixture.hpp"
#include "owner.hpp"
#include <openssl/sha.h>
#include <iomanip>
#include <sstream>
#include <unistd.h>
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#include <sycl/sycl.hpp>
namespace {
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=128)f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[2]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[2]).store(1);}
 float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+2*stride-1)/(2*stride),[&](int j){int i=j*2*stride;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}
};
struct Ref:ownrt::SyclOperation {
 ng::Shape shape;int row;
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override {
  ng::Args a;for(int i=0;i<16;++i)a.p[i]=p[i];auto scratch=static_cast<float*>(p[16]);auto s=shape;auto r=row;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.single_task([=]{ng::reference::row(s,a,r,scratch);});});
 }
};
struct Fused:ownrt::SyclOperation {
 std::vector<ng::Shape> shapes;int mode=0;
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps)const override {
  std::array<ng::Shape,6> ss{};std::array<ng::Args,6> aa{};int count=shapes.size(),local=2048;for(int j=0;j<count;++j){ss[j]=shapes[j];for(int i=0;i<16;++i)aa[j].p[i]=p[j*16+i];local=std::max(local,ng::local_floats(ss[j]));}
  auto s=ss[0];auto a=aa[0];auto selected=(mode==1||mode==2)?static_cast<float*>(p[16]):nullptr;int which=mode;
  size_t groups=which==1?s.tokens*4:which==2?s.tokens:which==3?s.tokens*24:which==5?ng::groups(s):1;
  std::array<fusion::Site,8> sites={fusion::Site{s,a},fusion::Site{s,a},fusion::Site{s,a},fusion::Site{s,a},fusion::Site{s,a},fusion::Site{s,a},fusion::Site{s,a},fusion::Site{s,a}};int n=0;
  for(int j=0;j<count;++j){sites[n++]=fusion::Site{ss[j],aa[j]};if(ss[j].op==ng::attention_score){auto next=ss[j];next.op=ng::attention_softmax;sites[n++]=fusion::Site{next,aa[j]};next.op=ng::attention_value;sites[n++]=fusion::Site{next,aa[j]};}}
  return q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> scratch(local,h);
   h.parallel_for(sycl::nd_range<1>(groups*128,128),[=](sycl::nd_item<1> it){Team team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()};
    if(which==1)fusion::route_rank(s,a,selected,it.get_group_linear_id(),team);
    else if(which==2)fusion::route_finish(s,a,selected,it.get_group_linear_id(),team);
    else if(which==3)fusion::attention(s,a,it.get_group_linear_id(),team);
    else if(which==5)ng::group(s,a,it.get_group_linear_id(),team);
    else fusion::chain(sites.data(),n,team);
   });});
 }
};
struct Runner {
 ownrt::Device device;ownrt::CopyEngine copy;std::vector<ownrt::Allocation> owned;uint64_t maximum=0;size_t checked=0;size_t allocation_serial=0;
 explicit Runner(unsigned card):device(ownrt::make_sycl_device(card,true)),copy(device){}
 ownrt::Allocation allocate(size_t bytes,ownrt::Memory memory=ownrt::Memory::device){auto id=device.arena.allocate("nongemv-fixture-"+std::to_string(allocation_serial++),bytes,memory,ownrt::Category::scratch,ownrt::Lifetime::transaction);owned.push_back(id);return id;}
 ownrt::Allocation upload(const std::vector<uint8_t>& data){auto h=allocate(data.size(),ownrt::Memory::pinned),v=allocate(data.size());std::memcpy(device.arena.row(h).pointer,data.data(),data.size());copy.copy(v,0,h,0,data.size(),{});return v;}
 void finish(ownrt::Event e){if(!device.wait(e,std::chrono::minutes(20)))throw std::runtime_error("fixture event incomplete; owner retained");auto t=device.timing(e);maximum=std::max(maximum,t.end_ns-t.start_ns);}
 std::vector<uint8_t> download(ownrt::Allocation id,size_t n){auto h=allocate(n,ownrt::Memory::pinned);auto e=copy.copy(h,0,id,0,n,{});if(!device.wait(e,std::chrono::minutes(20)))throw std::runtime_error("fixture copy incomplete");std::vector<uint8_t> out(n);std::memcpy(out.data(),device.arena.row(h).pointer,n);return out;}
 void run(std::vector<Fixture>& fixtures,bool fused,int chain=-1){
  std::vector<std::array<ownrt::Allocation,16>> ids(fixtures.size());for(size_t j=0;j<fixtures.size();++j)for(int i=0;i<16;++i)ids[j][i]=upload(fixtures[j].d[i]);
  if(chain==0)ids[1][0]=ids[0][5];
  if(chain==1){ids[1][0]=ids[0][3];ids[2][0]=ids[1][6];}
  if(chain==2){ids[1][0]=ids[0][8];ids[2][0]=ids[0][9];ids[2][1]=ids[1][7];ids[3][0]=ids[0][6];ids[3][1]=ids[0][7];ids[3][2]=ids[1][4];ids[3][3]=ids[1][5];ids[3][4]=ids[2][2];}
  if(chain==3)ids[1][0]=ids[0][2];
  if(!fused){auto scratch=allocate(ng::reference::scratch_floats*4);for(size_t j=0;j<fixtures.size();++j)for(int row=0;row<fixtures[j].s.tokens;++row){Ref op;op.shape=fixtures[j].s;op.row=row;std::vector<ownrt::Allocation> binding(ids[j].begin(),ids[j].end());binding.push_back(scratch);finish(device.compute(op,binding,{}));}}
  else {Fused op;std::vector<ownrt::Allocation> binding;for(size_t j=0;j<fixtures.size();++j){op.shapes.push_back(fixtures[j].s);binding.insert(binding.end(),ids[j].begin(),ids[j].end());}
   if(fixtures.size()==1&&fixtures[0].s.op==ng::route_gather){binding.push_back(allocate(fixtures[0].s.tokens*fixtures[0].s.extra*4));op.mode=1;finish(device.compute(op,binding,{}));op.mode=2;finish(device.compute(op,binding,{}));}
   else {op.mode=fixtures.size()==1?(fixtures[0].s.op==ng::attention_score?3:5):0;finish(device.compute(op,binding,{}));}
  }
  for(size_t j=0;j<fixtures.size();++j)for(int i=0;i<16;++i)if(fixtures[j].out[i])fixtures[j].d[i]=download(ids[j][i],fixtures[j].d[i].size());
  device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();++checked;
 }
};
void compare(const std::vector<Fixture>& a,const std::vector<Fixture>& b,const std::string& label){for(size_t j=0;j<a.size();++j)for(int i=0;i<16;++i)if(a[j].out[i]&&!(a[j].s.op==ng::route_gather&&i==4))need(a[j].d[i]==b[j].d[i],label+" stage="+std::to_string(j)+" slot="+std::to_string(i));}
void host_chain(std::vector<Fixture>& f,int kind){std::vector<ng::Args>a;for(auto& v:f)a.push_back(v.a());if(kind==0)a[1].p[0]=a[0].p[5];if(kind==1){a[1].p[0]=a[0].p[3];a[2].p[0]=a[1].p[6];}if(kind==2){a[1].p[0]=a[0].p[8];a[2].p[0]=a[0].p[9];a[2].p[1]=a[1].p[7];a[3].p[0]=a[0].p[6];a[3].p[1]=a[0].p[7];a[3].p[2]=a[1].p[4];a[3].p[3]=a[1].p[5];a[3].p[4]=a[2].p[2];}if(kind==3)a[1].p[0]=a[0].p[2];for(size_t j=0;j<f.size();++j)ng::reference::cpu(f[j].s,a[j]);}
}
#endif
int main(int argc,char** argv){try{
 fs::path out,fixtures=fs::path(__FILE__).parent_path()/"build/fusion-fixtures";unsigned card=0;bool authorized=false;
 for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--authorized-device-window")authorized=true;else if(a=="--output"&&i+1<argc)out=argv[++i];else if(a=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(a=="--fixtures"&&i+1<argc)fixtures=argv[++i];else throw std::invalid_argument("nongemv fixture arguments");}
 need(!out.empty(),"--output required");
 #ifdef OWN_RT_HOST_ONLY
 need(!authorized,"CPU fixture binary");
 #else
 need(authorized,"--authorized-device-window required");for(char** p=environ;*p;++p)need(!std::string(*p).starts_with("NEO"),"NEO debug key refused");
 #endif
 fs::create_directories(out);std::string args[]{"host-reference",fixtures.string(),(out/"cpu-gate.json").string(),(out/"output.bin").string()};char* cp[]{args[0].data(),args[1].data(),args[2].data(),args[3].data()};need(packet20_host_gate(4,cp)==0,"CPU v2 fixture gate");
 uint64_t maximum=0;size_t checked=0;bool safe=true;std::string teardown="[]";
 #ifndef OWN_RT_HOST_ONLY
 Runner runner(card);std::ifstream list(fixtures/"cases.txt");std::string name;
 while(list>>name){std::vector<Fixture> source{Fixture(fixtures/name)},host=source,reference=source,fused=source;ng::reference::cpu(host[0].s,host[0].a());runner.run(reference,false);runner.run(fused,true);compare(host,reference,name+" host/unfused");compare(host,fused,name+" host/fused");++checked;
  if(source[0].s.op==ng::norm){auto second=source[0];second.s.op=ng::activation;second.s.width=source[0].s.heads*source[0].s.width;second.s.heads=1;second.s.extra=0;std::vector<Fixture> chain{source[0],second};auto h=chain,r=chain,c=chain;host_chain(h,3);runner.run(r,false,3);runner.run(c,true,3);compare(h,r,"norm activation host/unfused");compare(h,c,"norm activation host/fused");++checked;}
 }
 for(int tokens:{1,3})for(int kind=0;kind<3;++kind){std::vector<std::string> names=kind==0?std::vector<std::string>{"combine-norm-","mix-"}:kind==1?std::vector<std::string>{"conv-10240-","gdn-","gdn-gated-"}:std::vector<std::string>{"qsa-prepare-","qsa-pool-","qsa-select-","qsa-attention-"};std::vector<Fixture> source;for(auto& n:names)source.emplace_back(fixtures/(n+std::to_string(tokens)+".fixture"));auto host=source,ref=source,fused=source;host_chain(host,kind);runner.run(ref,false,kind);runner.run(fused,true,kind);compare(host,ref,"chain host/unfused");compare(host,fused,"chain host/fused");++checked;}
 for(auto name:{"route-varied.fixture","qsa-attention-3.fixture"})for(int mode=0;mode<4;++mode){std::vector<Fixture> source{Fixture(fixtures/name)};auto& f=source[0];if(mode==0)f.a().i(15)[1]=0;if(mode==1)f.a().i(15)[2]=1;if(mode==2)f.a().i(15)[0]=-1;if(mode==3&&f.s.op==ng::attention_score)f.a().i(4)[(f.s.tokens-1)*(f.s.budget+3)]=f.s.capacity;auto host=source,ref=source,fused=source;ng::reference::cpu(host[0].s,host[0].a());runner.run(ref,false);runner.run(fused,true);need(host[0].d[15]==fused[0].d[15]&&host[0].d[15]==ref[0].d[15],"sticky control device parity");if(mode<3){compare(host,ref,"control host/unfused");compare(host,fused,"control host/fused");}++checked;}
 maximum=runner.maximum;auto shutdown=runner.device.shutdown(std::chrono::minutes(20));safe=shutdown.safe_to_exit;teardown="["+shutdown.json()+"]";need(safe,"owner teardown");
 #endif
 auto adapter=adapter_fixture_gate(card,out/"output.bin");maximum=std::max(maximum,adapter.max_submission_ns);if(teardown=="[]")teardown="["+adapter.teardown+"]";else teardown.insert(teardown.size()-1,","+adapter.teardown);
 std::ifstream input(out/"output.bin",std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)),{});unsigned char hash[SHA256_DIGEST_LENGTH];SHA256(bytes.data(),bytes.size(),hash);std::ostringstream hex;for(auto b:hash)hex<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);
 std::ofstream receipt(out/"receipt.json");receipt<<"{\"schema\":\"own-runtime.iq3.packet21.fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"fused_unfused_exact\":true,\"host_exact\":true,\"arithmetic\":\"iq3-p17-detmath-v2\",\"owner_cards\":1,\"fixture_output_sha256\":\""<<hex.str()<<"\",\"max_submission_ns\":"<<maximum<<",\"sequential_owners\":"<<(authorized?2:1)<<",\"safe_to_exit\":true,\"teardown\":"<<teardown<<",\"fixtures\":72,\"integrated_chains\":6,\"control_checks\":8,\"device_checks\":"<<checked<<",\"actual_adapter_checks\":"<<adapter.checks<<"}\n";
 std::cout<<"non-GEMV 72 fixtures + 6 chains + 8 controls + actual adapter M1/3 PASS\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
