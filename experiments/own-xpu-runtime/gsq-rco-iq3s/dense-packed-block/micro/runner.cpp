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
  need(offset<=size_t(a.st_size)&&bytes<=size_t(a.st_size)-offset&&bytes<=18022400,"bounded read");std::vector<uint8_t>v(bytes);size_t done=0;
  while(done<bytes){guard();auto n=pread(fd,v.data()+done,std::min(size_t(1<<20),bytes-done),offset+done);need(n>0,"short fixed read");done+=n;}
  need(!fstat(fd,&b)&&!lstat(path,&c)&&same(a,b)&&same(a,c)&&sha(v)==digest,"fixed input changed/hash mismatch");::close(fd);return v;
 }catch(...){::close(fd);throw;}
}
}
#include "startup.hpp"
namespace micro {
struct Data{std::vector<uint8_t>w,x,expected;};
struct Case{Allocation w,x,ya,yb;std::array<PreparedCompute,2>cmd;};
void original_identity(const Fixed&s){
 need(fs::canonical(s.shard)==fs::path(s.shard),"canonical model identity");int fd=::open(s.shard,O_RDONLY|O_NOFOLLOW);need(fd>=0,"model identity open");
 try{struct stat a{},b{};need(!fstat(fd,&a)&&S_ISREG(a.st_mode)&&!lstat(s.shard,&b)&&same(a,b),"held model identity");
 need(uint64_t(a.st_dev)==s.dev&&uint64_t(a.st_ino)==s.ino&&uint64_t(a.st_size)==s.size&&uint64_t(a.st_mtim.tv_sec)*1000000000+a.st_mtim.tv_nsec==s.mtime&&uint64_t(a.st_ctim.tv_sec)*1000000000+a.st_ctim.tv_nsec==s.ctime,"source model unchanged since sparse extraction");::close(fd);
 }catch(...){::close(fd);throw;}
}
struct Harness {
 Device&d;Allocation slab;size_t &allocated,&transfers,&submissions;unsigned serial=0;
 Harness(Device&v,size_t&a,size_t&t,size_t&n):d(v),allocated(a),transfers(t),submissions(n){slab=d.arena.allocate("micro:transfer",1048576,Memory::pinned,Category::pinned_slab,Lifetime::transfer);}
 Allocation alloc(size_t n){guard();allocated+=n;need(allocated<=35331072,"device budget");return d.arena.allocate("micro:"+std::to_string(serial++),n,Memory::device,Category::scratch,Lifetime::transaction);}
 void complete(Event e){need(d.wait(e,std::chrono::seconds(30))&&d.complete(e)&&d.in_flight()==0,"event incomplete");d.retire_completed_events();guard();}
 void upload(Allocation id,const std::vector<uint8_t>&v){need(v.size()==d.arena.row(id).bytes,"upload extent");for(size_t off=0;off<v.size();){guard();need(d.in_flight()==0,"restage pending");size_t n=std::min(size_t(1048576),v.size()-off);transfers+=n;need(transfers<=37764096,"transfer budget");std::memcpy(d.arena.row(slab).pointer,v.data()+off,n);CopyEngine cp(d);complete(cp.copy(id,off,slab,0,n,{}));off+=n;}}
 std::vector<uint8_t> output(Allocation id){guard();size_t n=d.arena.row(id).bytes;need(d.in_flight()==0&&(n==12288||n==20480),"output/status extent/pending");transfers+=n;need(transfers<=37764096,"transfer budget");CopyEngine cp(d);complete(cp.copy(slab,0,id,0,n,{}));auto*p=static_cast<uint8_t*>(d.arena.row(slab).pointer);return {p,p+n};}
 Case setup(const Data&v,const Fixed&spec){
  Case c{};c.w=alloc(v.w.size());c.x=alloc(v.x.size());c.ya=alloc(spec.rows*2);c.yb=alloc(spec.rows*2);upload(c.w,v.w);upload(c.x,v.x);
  for(unsigned arm=0;arm<2;++arm){std::vector<PreparedCompute>cmd;d.begin_capture(cmd);
   try{auto y=arm?c.yb:c.ya;
    integrated::Matrix m{};m.type=static_cast<iq3::Type>(spec.type);m.rows=spec.rows;m.columns=2560;m.count=m.experts=1;m.span=m.rows;m.w=c.w;m.x=c.x;m.y=y;
    if(arm)denseblock::submit(d,m,spec.label,spec.weight,gsqn::InputMode::shared);
    else gsqn::submit(d,m,gsqn::InputMode::shared,gsqn::Storage::packed_direct);
    d.end_capture();}catch(...){d.end_capture();throw;}
   need(cmd.size()==1,"one captured original/candidate kernel");c.cmd[arm]=std::move(cmd[0]);}
  return c;
 }
 EventTiming timed(const PreparedCompute&cmd){guard();++submissions;auto e=d.issue(cmd);need(d.wait(e,std::chrono::seconds(30))&&d.complete(e)&&d.in_flight()==0,"kernel incomplete");auto t=d.timing(e);need(t.start_ns>0&&t.end_ns>t.start_ns,"positive profiling interval");d.retire_completed_events();guard();return t;}
};
int run(unsigned card,const fs::path&out){
 need(out.is_absolute()&&!fs::exists(out)&&out.parent_path()==fs::canonical(out.parent_path()),"fresh canonical output");need(fs::create_directory(out),"output creation");deadline=std::chrono::steady_clock::now()+std::chrono::minutes(15);
 bool entered=false,safe=true,passed=false,acknowledged=false;std::string error,cleanup,teardown;std::unique_ptr<Device>d;Backend*backend=nullptr;size_t pairs=0,allocated=0,transfers=0,submissions=0;
 std::ofstream samples(out/"samples.jsonl");need(bool(samples),"samples file");
 auto report=[&]()noexcept{try{std::ofstream f(out/"result.json");f<<"{\"schema\":\"gsq.dense-packed-block.native-micro.v1\",\"passed\":"<<(passed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"card\":"<<card<<",\"backend_acknowledged\":"<<(acknowledged?"true":"false")<<",\"profiling\":true,\"model_executed\":false,\"device_factory_entered\":"<<(entered?"true":"false")<<",\"completed_exact_pairs\":"<<pairs<<",\"attempted_kernel_submissions\":"<<submissions<<",\"device_bytes\":"<<allocated<<",\"transfer_bytes\":"<<transfers<<",\"warmup_cycles\":4,\"measured_cycles\":24,\"error\":"<<quote(error)<<",\"cleanup_error\":"<<quote(cleanup)<<",\"teardown\":"<<(teardown.empty()?"null":teardown)<<"}\n";f.flush();return bool(f);}catch(...){return false;}};
 try{
  std::array<Data,3>data;for(size_t i=0;i<3;++i){auto&s=fixed[i];original_identity(s);need(s.layer==i&&s.type==(i==0?12u:i==1?13u:23u)&&s.rows==(i==1?10240u:6144u),"fixed three type/shape cases");
   auto&v=data[i];v.x=read(s.x,0,5120,s.x_sha);v.expected=read(s.y,0,s.rows*2,s.y_sha);
   v.w=read(s.packed,0,gsq::row_bytes(s.type,2560)*s.rows,s.weight_sha);original_identity(s);
  }
  guard();entered=true;safe=false;auto owner=make_sycl_device(card,true);backend=owner.get();d=std::make_unique<Device>(std::move(owner));await_backend_ack(out);acknowledged=true;Harness h(*d,allocated,transfers,submissions);std::array<Case,3>cases;
  for(size_t i=0;i<3;++i)cases[i]=h.setup(data[i],fixed[i]);
  for(unsigned phase=0;phase<2;++phase)for(unsigned cycle=0;cycle<(phase?24u:4u);++cycle)for(unsigned j=0;j<3;++j){
   unsigned i=((cycle/2)+j)%3;auto&c=cases[i];std::array<EventTiming,2>t;
   for(unsigned k=0;k<2;++k){unsigned arm=cycle%2?1-k:k;t[arm]=h.timed(c.cmd[arm]);}
   auto a=h.output(c.ya),b=h.output(c.yb);bool exact=a==b&&a==data[i].expected;
   samples<<"{\"warmup\":"<<(phase?"false":"true")<<",\"cycle\":"<<cycle<<",\"layer\":"<<fixed[i].layer<<",\"label\":"<<quote(fixed[i].label)<<",\"order\":"<<quote(cycle%2?"BA":"AB")<<",\"A_start_ns\":"<<t[0].start_ns<<",\"A_end_ns\":"<<t[0].end_ns<<",\"B_start_ns\":"<<t[1].start_ns<<",\"B_end_ns\":"<<t[1].end_ns<<",\"A_sha256\":"<<quote(sha(a))<<",\"B_sha256\":"<<quote(sha(b))<<",\"expected_sha256\":"<<quote(fixed[i].y_sha)<<",\"exact\":"<<(exact?"true":"false")<<"}\n";samples.flush();need(bool(samples),"samples write");
   allocated=h.allocated;transfers=h.transfers;submissions=h.submissions;
   if(!exact){for(auto pair:{std::pair{"A",&a},std::pair{"B",&b}}){std::ofstream f(out/(std::string("mismatch-")+pair.first+".bin"),std::ios::binary);f.write(reinterpret_cast<const char*>(pair.second->data()),pair.second->size());}throw std::runtime_error("exact BF16 baseline gate failed; no further pair");}
   ++pairs;need(report(),"progress receipt");
  }
  guard();backend->synchronize();auto r=d->shutdown(std::chrono::seconds(30));teardown=r.json();safe=r.safe_to_exit;need(safe&&r.exit_code==0&&r.in_flight==0&&r.live_bytes==0,"owner teardown");need(pairs==84&&submissions==168&&allocated==35331072&&transfers==37764096,"complete fixed schedule and byte ledger");passed=true;
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
