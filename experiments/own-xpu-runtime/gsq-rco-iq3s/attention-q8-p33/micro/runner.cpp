#include "selected.hpp"
#include "fixed.hpp"
#include <openssl/evp.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <csignal>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/resource.h>
namespace micro {
using namespace ownrt;namespace fs=std::filesystem;
volatile std::sig_atomic_t stopped=0;
auto deadline=std::chrono::steady_clock::time_point::max();
void stop(int){stopped=1;}
void need(bool v,const char*s){if(!v)throw std::runtime_error(s);}
void guard(){need(!stopped&&std::chrono::steady_clock::now()<deadline,"stop/deadline; no new submissions");}
std::string sha(const std::vector<uint8_t>&v){unsigned char b[32];unsigned n=0;need(EVP_Digest(v.data(),v.size(),b,&n,EVP_sha256(),nullptr)==1&&n==32,"SHA256 failed");std::string s;for(auto x:b){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
bool same(const struct stat&a,const struct stat&b){return a.st_dev==b.st_dev&&a.st_ino==b.st_ino&&a.st_size==b.st_size&&a.st_mtim.tv_sec==b.st_mtim.tv_sec&&a.st_mtim.tv_nsec==b.st_mtim.tv_nsec&&a.st_ctim.tv_sec==b.st_ctim.tv_sec&&a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;}
std::vector<uint8_t> read(const char*path,size_t offset,size_t bytes,const char*digest,const Fixed*spec=nullptr){
 guard();need(fs::canonical(path)==fs::path(path),"canonical fixed input");int fd=::open(path,O_RDONLY|O_NOFOLLOW);need(fd>=0,"open fixed input");
 try{struct stat a{},b{},c{};need(!fstat(fd,&a)&&S_ISREG(a.st_mode),"regular input");
  if(spec)need(uint64_t(a.st_dev)==spec->dev&&uint64_t(a.st_ino)==spec->ino&&uint64_t(a.st_size)==spec->size&&uint64_t(a.st_mtim.tv_sec)*1000000000+a.st_mtim.tv_nsec==spec->mtime&&uint64_t(a.st_ctim.tv_sec)*1000000000+a.st_ctim.tv_nsec==spec->ctime,"model identity");
  else need(size_t(a.st_size)==bytes&&offset==0,"fixture exact extent");
  need(offset<=size_t(a.st_size)&&bytes<=size_t(a.st_size)-offset&&bytes<=16711680,"bounded read");std::vector<uint8_t>v(bytes);size_t done=0;
  while(done<bytes){guard();auto n=pread(fd,v.data()+done,std::min(size_t(1<<20),bytes-done),offset+done);need(n>0,"short fixed read");done+=n;}
  need(!fstat(fd,&b)&&!lstat(path,&c)&&same(a,b)&&same(a,c)&&sha(v)==digest,"fixed input changed/hash mismatch");::close(fd);return v;
 }catch(...){::close(fd);throw;}
}
struct Data{std::vector<uint8_t>w,expanded,x,expected;};
struct Case{Allocation w,x,ya,yb,workspace;std::array<PreparedCompute,2>cmd;};
struct Harness {
 Device&d;Allocation slab;size_t &allocated,&transfers,&submissions;unsigned serial=0;
 Harness(Device&v,size_t&a,size_t&t,size_t&n):d(v),allocated(a),transfers(t),submissions(n){slab=d.arena.allocate("micro:transfer",1048576,Memory::pinned,Category::pinned_slab,Lifetime::transfer);}
 Allocation alloc(size_t n){guard();allocated+=n;need(allocated<=106481664,"device budget");return d.arena.allocate("micro:"+std::to_string(serial++),n,Memory::device,Category::scratch,Lifetime::transaction);}
 void complete(Event e){need(d.wait(e,std::chrono::seconds(30))&&d.complete(e)&&d.in_flight()==0,"event incomplete");d.retire_completed_events();guard();}
 void upload(Allocation id,const std::vector<uint8_t>&v){need(v.size()==d.arena.row(id).bytes,"upload extent");for(size_t off=0;off<v.size();){guard();need(d.in_flight()==0,"restage pending");size_t n=std::min(size_t(1048576),v.size()-off);transfers+=n;need(transfers<=134217728,"transfer budget");std::memcpy(d.arena.row(slab).pointer,v.data()+off,n);CopyEngine cp(d);complete(cp.copy(id,off,slab,0,n,{}));off+=n;}}
 std::vector<uint8_t> output(Allocation id){guard();need(d.in_flight()==0&&d.arena.row(id).bytes==5120,"output extent/pending");transfers+=5120;need(transfers<=134217728,"transfer budget");CopyEngine cp(d);complete(cp.copy(slab,0,id,0,5120,{}));auto*p=static_cast<uint8_t*>(d.arena.row(slab).pointer);return {p,p+5120};}
 Case setup(const Data&v){
  Case c{};c.w=alloc(v.w.size());auto ew=alloc(v.expanded.size());c.x=alloc(v.x.size());c.ya=alloc(5120);c.yb=alloc(5120);c.workspace=alloc(81920);upload(c.w,v.w);upload(ew,v.expanded);upload(c.x,v.x);
  integrated::Matrix m{};m.type=iq3::Type::Q8_0;m.w=ew;m.x=c.x;m.y=c.yb;m.workspace=c.workspace;m.rows=2560;m.columns=6144;m.experts=1;m.count=1;m.span=2560;m.activation=m.output_type=iq3::Type::BF16;
  for(unsigned arm=0;arm<2;++arm){std::vector<PreparedCompute>cmd;d.begin_capture(cmd);try{if(arm==0)iq3::kopt::gemv(d,iq3::Type::Q8_0,c.w,c.x,c.ya,2560,6144,iq3::Type::BF16,iq3::Type::BF16,32,0);else{auto launch=p33::submit(d,{m},"p33.dense.segment",false,6);need(launch.passes==1,"candidate single pass");}d.end_capture();}catch(...){d.end_capture();throw;}need(cmd.size()==1,"exactly one captured kernel");c.cmd[arm]=std::move(cmd[0]);}
  return c;
 }
 EventTiming timed(const PreparedCompute&cmd){guard();++submissions;auto e=d.issue(cmd);need(d.wait(e,std::chrono::seconds(30))&&d.complete(e)&&d.in_flight()==0,"kernel incomplete");auto t=d.timing(e);need(t.start_ns>0&&t.end_ns>t.start_ns,"positive profiling interval");d.retire_completed_events();guard();return t;}
};
int run(unsigned card,const fs::path&out){
 need(out.is_absolute()&&!fs::exists(out)&&out.parent_path()==fs::canonical(out.parent_path()),"fresh canonical output");need(fs::create_directory(out),"output creation");deadline=std::chrono::steady_clock::now()+std::chrono::minutes(15);
 bool entered=false,safe=true,passed=false;std::string error,cleanup,teardown;std::unique_ptr<Device>d;Backend*backend=nullptr;size_t pairs=0,allocated=0,transfers=0,submissions=0;
 std::ofstream samples(out/"samples.jsonl");need(bool(samples),"samples file");
 auto report=[&]()noexcept{try{std::ofstream f(out/"result.json");f<<"{\"schema\":\"gsq.attention-q8.native-micro.v1\",\"passed\":"<<(passed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"card\":"<<card<<",\"profiling\":true,\"model_executed\":false,\"device_factory_entered\":"<<(entered?"true":"false")<<",\"completed_exact_pairs\":"<<pairs<<",\"attempted_kernel_submissions\":"<<submissions<<",\"device_bytes\":"<<allocated<<",\"transfer_bytes\":"<<transfers<<",\"warmup_cycles\":4,\"measured_cycles\":24,\"error\":"<<quote(error)<<",\"cleanup_error\":"<<quote(cleanup)<<",\"teardown\":"<<(teardown.empty()?"null":teardown)<<"}\n";f.flush();return bool(f);}catch(...){return false;}};
 try{
  std::array<Data,3>data;for(size_t i=0;i<3;++i){auto&s=fixed[i];data[i].x=read(s.x,0,12288,s.x_sha);data[i].expected=read(s.y,0,5120,s.y_sha);data[i].w=read(s.shard,s.offset,16711680,s.weight_sha,&s);data[i].expanded=iq3::expanded::expand(iq3::Type::Q8_0,data[i].w.data(),data[i].w.size(),6144);need(data[i].expanded.size()==18677760,"expanded exact extent");}
  guard();entered=true;safe=false;auto owner=make_sycl_device(card,true);backend=owner.get();d=std::make_unique<Device>(std::move(owner));Harness h(*d,allocated,transfers,submissions);std::array<Case,3>cases;
  for(size_t i=0;i<3;++i)cases[i]=h.setup(data[i]);
  for(unsigned phase=0;phase<2;++phase)for(unsigned cycle=0;cycle<(phase?24u:4u);++cycle)for(unsigned j=0;j<3;++j){
   unsigned i=(cycle+j)%3;auto&c=cases[i];std::array<EventTiming,2>t;
   for(unsigned k=0;k<2;++k){unsigned arm=cycle%2?1-k:k;t[arm]=h.timed(c.cmd[arm]);}
   auto a=h.output(c.ya),b=h.output(c.yb);bool exact=a==b&&a==data[i].expected;
   samples<<"{\"warmup\":"<<(phase?"false":"true")<<",\"cycle\":"<<cycle<<",\"layer\":"<<fixed[i].layer<<",\"order\":"<<quote(cycle%2?"BA":"AB")<<",\"A_start_ns\":"<<t[0].start_ns<<",\"A_end_ns\":"<<t[0].end_ns<<",\"B_start_ns\":"<<t[1].start_ns<<",\"B_end_ns\":"<<t[1].end_ns<<",\"A_sha256\":"<<quote(sha(a))<<",\"B_sha256\":"<<quote(sha(b))<<",\"expected_sha256\":"<<quote(fixed[i].y_sha)<<",\"exact\":"<<(exact?"true":"false")<<"}\n";samples.flush();need(bool(samples),"samples write");
   allocated=h.allocated;transfers=h.transfers;submissions=h.submissions;
   if(!exact){for(auto pair:{std::pair{"A",&a},std::pair{"B",&b}}){std::ofstream f(out/(std::string("mismatch-")+pair.first+".bin"),std::ios::binary);f.write(reinterpret_cast<const char*>(pair.second->data()),pair.second->size());}throw std::runtime_error("exact BF16 baseline gate failed; no further pair");}
   ++pairs;need(report(),"progress receipt");
  }
  guard();backend->synchronize();auto r=d->shutdown(std::chrono::seconds(30));teardown=r.json();safe=r.safe_to_exit;need(safe&&r.exit_code==0&&r.in_flight==0&&r.live_bytes==0,"owner teardown");need(pairs==84&&submissions==168,"complete fixed schedule");passed=true;
 }catch(const std::exception&e){error=e.what();}catch(...){error="non-standard micro failure";}
 if(!passed){if(!d){if(entered){report();hold_for_supervisor();}safe=true;}else if(teardown.empty()){
  try{backend->synchronize();}catch(const std::exception&e){cleanup=e.what();report();hold_for_supervisor();}catch(...){cleanup="backend synchronization uncertain";report();hold_for_supervisor();}
  try{auto r=d->shutdown(std::chrono::seconds(30));teardown=r.json();safe=r.safe_to_exit;}catch(const std::exception&e){cleanup=e.what();safe=false;}catch(...){cleanup="shutdown failed";safe=false;}
 }}
 bool recorded=report();if(!safe)hold_for_supervisor();return passed&&recorded?0:1;
}
}
int main(int argc,char**argv){
 if(argc!=6||std::string(argv[1])!="--run"||std::string(argv[2])!="--card"||std::string(argv[4])!="--output")return 64;
 try{std::string v=argv[3];if(v.empty()||v.find_first_not_of("0123456789")!=std::string::npos)return 64;auto c=std::stoul(v);if(c>3)return 64;struct rlimit r{};micro::need(getrlimit(RLIMIT_AS,&r)==0&&r.rlim_cur==RLIM_INFINITY,"native requires unlimited AS");umask(0077);std::signal(SIGTERM,micro::stop);std::signal(SIGINT,micro::stop);return micro::run(c,argv[5]);}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
