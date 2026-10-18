// Tiny two-process transport diagnostic. No model, target arithmetic or weights.
#include "sources/owner.hpp"
#include "sources/sycl_operation.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
namespace fs=std::filesystem;
void require(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
namespace pipeline {
constexpr size_t slot_bytes=65536;
enum {half=1,accept=2,rollback=3,dump=4,draft=9};
struct Request {int32_t op,token,position,fixture,speculative,sequence,reserved[2];};
struct Reply {int32_t status,token,error,bytes,sequence,rank,reserved[2];double busy_ms,gpu_ms,redo_ms,reserved_ms;};
}
#include "sources/native_controller.hpp"
using namespace ownrt;
namespace n=pipeline::native38;
static volatile std::sig_atomic_t stopped=0;
void stop(int){stopped=1;}
void guard(){require(!stopped,"graceful stop requested");}
constexpr size_t MAX_BYTES=20480, WORK=65536;
struct Shared {n::Mailbox box; alignas(64) uint8_t data[3*pipeline::slot_bytes+4096]{};
 double export_begin=0,export_end=0,import_begin=0,import_end=0,received=0;
 uint32_t ready=0,child_drained=0;};
// Uses the same in-order Device queue. Thus own-card compute cannot be bypassed
// by a transfer; the other card can still compute concurrently. No extra queue.
struct Busy: SyclOperation {
 sycl::event submit(sycl::queue&q,std::span<void*const> p,const std::vector<sycl::event>&deps)const override{
 auto*out=static_cast<uint32_t*>(p[0]);
 return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::range<1>(WORK),[=](sycl::id<1> id){uint32_t x=uint32_t(id[0])+1;for(int i=0;i<2048;++i)x=x*1664525u+1013904223u+(x>>13);out[id[0]]=x;});});
 }
};
struct Rank {
 Device d; CopyEngine copies; Allocation buffer,slab,work; Event pending=0; Shared&s; size_t bytes=0;int seed=0;
 Rank(Shared&shared):d(make_sycl_device(0,false)),copies(d),s(shared){
 buffer=d.arena.allocate("card0:transport",MAX_BYTES,Memory::device,Category::scratch,Lifetime::transaction);
 slab=d.arena.allocate("staging",MAX_BYTES,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
 work=d.arena.allocate("card0:compute",WORK*4,Memory::device,Category::scratch,Lifetime::transaction);
 }
 void wait(Event e){require(d.wait(e,std::chrono::seconds(10)),"device wait timeout");}
 uint8_t*host(){return static_cast<uint8_t*>(d.arena.row(slab).pointer);}
 void retire(){if(pending){wait(pending);pending=0;}d.retire_ordered_events();}
 void prep(int size,int value){retire();bytes=size;seed=value;for(size_t i=0;i<bytes;++i)host()[i]=uint8_t(seed+i*17);wait(copies.copy(buffer,0,slab,0,bytes,{}));d.retire_ordered_events();}
 void compute(){Busy op;std::array<Allocation,1> ids{work};pending=d.compute(op,ids,{});}
 void out(){s.export_begin=n::clock_now();wait(copies.copy(slab,0,buffer,0,bytes,{}));d.retire_ordered_events();pending=0;std::memcpy(s.data,host(),bytes);s.export_end=n::clock_now();}
 void in(){s.import_begin=n::clock_now();std::memcpy(host(),s.data+pipeline::slot_bytes,bytes);wait(copies.copy(buffer,0,slab,0,bytes,{}));s.import_end=n::clock_now();pending=0;d.retire_ordered_events();}
 void verify(){wait(copies.copy(slab,0,buffer,0,bytes,{}));for(size_t i=0;i<bytes;++i)require(host()[i]==uint8_t(seed+i*17),"transport byte mismatch");d.retire_ordered_events();}
 pipeline::Reply execute(const pipeline::Request&r){s.received=n::clock_now();switch(r.op){
 case 10:out();break;case 11:in();break;case 12:compute();break;
 case 13:prep(r.token,r.position);break;case 14:break;case 15:seed=r.token;verify();break;case 16:retire();break;
 default:throw std::runtime_error("unknown micro op");}return {};}
 bool shutdown(){retire();return d.shutdown(std::chrono::seconds(30)).safe_to_exit;}
};
void mask(int rank){setenv("NEOReadDebugKeys","1",1);setenv("FilterBdfPath",rank?"0000:47:00.0":"0000:43:00.0",1);setenv("ZE_ENABLE_PCI_ID_DEVICE_ORDER","1",1);setenv("ZE_AFFINITY_MASK","0",1);setenv("ONEAPI_DEVICE_SELECTOR","level_zero:0",1);}
int main(int argc,char**argv){
 if(argc!=2||std::string(argv[1])!="--coordinator-admitted-device-window"){std::cerr<<"REFUSED: coordinator admission required\n";return 2;}
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 auto*s=static_cast<Shared*>(mmap(nullptr,sizeof(Shared),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0));
 if(s==MAP_FAILED)return 1;new(s) Shared;
 const pid_t child=fork();if(child<0)return 1;
 if(child==0){try{mask(1);Rank rank(*s);n::publish(s->ready,1);
 n::worker(s->box,30,[&](const pipeline::Request&r){return rank.execute(r);},guard);
 require(rank.shutdown(),"rank1 drain incomplete");n::publish(s->child_drained,1);return 0;
 }catch(const std::exception&e){n::abort(s->box);std::cerr<<"rank1: "<<e.what()<<'\n';return 1;}}
 int status=0;
 try{mask(0);Rank rank(*s);require(p56x::wait([&]{return n::load(s->ready)==1;},[&]{guard();require(!n::load(s->box.abort),"child initialization failed");},std::chrono::steady_clock::now()+std::chrono::seconds(60)),"child startup timeout");
 n::Backend peer(s->box,s->data,10,[](const pipeline::Request&){return pipeline::Reply{};},guard);
 std::cout<<std::setprecision(17);
 // 200 measured repetitions per case and mode, in alternating case/mode order.
 // Ten discarded repetitions initialize kernels, queues and tiny memory only.
 for(int rep=-10;rep<200;++rep){std::array<int,5> cases{0,1,2,3,4};if(rep&1)std::reverse(cases.begin(),cases.end());
 for(int code:cases)for(int j=0;j<(code==4?1:2);++j){guard();bool concurrent=code==4?false:bool(j^(rep&1));int bytes=code==0?5120:code==1?8:code==2?16:20480;
 bool reverse=code==0;const char*name=code==0?"hidden":code==1?"best8":code==2?"best16":code==3?"pipeline20480":"mailbox20480";
 int seed=rep+400+code*7;rank.prep(bytes,seed);peer.call(1,13,bytes,seed); // source pattern
 // Poison destination so a no-op upload cannot pass the byte check.
 if(reverse)rank.prep(bytes,seed+1);else peer.call(1,13,bytes,seed+1);
 if(concurrent){peer.call(1,12);rank.compute();}
 double start=n::clock_now(),export_done=start,usable=start,host_boundary=0;
 if(code==4){for(int i=0;i<bytes;++i)s->data[i]=uint8_t(seed+i*17);peer.stream_bytes=bytes;start=n::clock_now();peer.handover();peer.call(1,14);usable=n::clock_now();host_boundary=s->received-start;export_done=start;}
 else if(reverse){peer.call(1,10);start=s->export_begin;export_done=n::clock_now();peer.stream_bytes=bytes;peer.handover();rank.in();usable=s->import_end;host_boundary=export_done-s->export_end;rank.seed=seed;rank.verify();}
 else{rank.out();start=s->export_begin;export_done=s->export_end;peer.stream_bytes=bytes;double ready=n::clock_now();peer.handover();peer.call(1,11);usable=s->import_end;host_boundary=s->received-ready;// Validation follows before any destination rewrite.
 }
 // Reverse verified above. Forward validation needs readback of the uploaded
 // destination, never reset it before verification (seed supplied separately).
 if(!reverse&&code!=4)peer.call(1,15,seed);
 rank.retire();peer.call(1,16);
 if(rep>=0)std::cout<<"{\"kind\":\"sample\",\"case\":\""<<name<<"\",\"rep\":"<<rep<<",\"concurrent\":"<<(concurrent?"true":"false")<<",\"bytes\":"<<bytes<<",\"source_card\":"<<(reverse?3:2)<<",\"destination_card\":"<<(reverse?2:3)<<",\"start_s\":"<<start<<",\"export_done_s\":"<<export_done<<",\"usable_s\":"<<usable<<",\"total_us\":"<<(usable-start)*1e6<<",\"export_us\":"<<(export_done-start)*1e6<<",\"import_us\":"<<(usable-export_done)*1e6<<",\"host_boundary_us\":"<<host_boundary*1e6<<",\"bytes_exact\":true}\n";
 }}
 peer.call(1,0);require(rank.shutdown(),"rank0 drain incomplete");require(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0&&n::load(s->child_drained),"rank1 drain unproved");
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"repetitions\":200,\"samples\":1800,\"profiling\":false,\"wait_policy\":\"spin\",\"same_queue_compute\":true}\n";munmap(s,sizeof(Shared));return 0;
 }catch(const std::exception&e){n::abort(s->box);std::cerr<<e.what()<<'\n';waitpid(child,&status,0);return 1;}
}
