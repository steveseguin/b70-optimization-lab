// Packet171b CPU ordering test. A mock in-order queue records every operation.
// It instantiates the SAME p171::foreground_copy/foreground_sync templates that
// native/generated/single_device.cpp instantiates with sycl::queue.
// Built normally it must pass. Built with -DP171_PARENT_ROUTING (the packet58as
// routing: BCS copy + compute barrier per copy, two-queue sync) the candidate
// assertions must FAIL, proving the test detects the old code.
#include "cq_copy.hpp"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

struct Op {std::string queue,kind;int event=0;std::vector<int> deps;};
static std::vector<Op> ops;
static int next_event=0;
struct Ev {int id=0;std::string queue;};
struct MockQueue {
  std::string name;bool fail_barrier=false;
  Ev memcpy(void* d,const void* s,std::size_t n,const std::vector<Ev>& after) {
    std::memcpy(d,s,n);Op o{name,"memcpy",++next_event,{}};for(auto& e:after)o.deps.push_back(e.id);ops.push_back(o);return {o.event,name};
  }
  Ev kernel() {Op o{name,"kernel",++next_event,{}};ops.push_back(o);return {o.event,name};}
  void ext_oneapi_submit_barrier(const std::vector<Ev>& deps) {
    Op o{name,"barrier",++next_event,{}};for(auto& e:deps)o.deps.push_back(e.id);ops.push_back(o);
    if(fail_barrier)throw std::runtime_error("barrier failure");
  }
  void wait() {ops.push_back({name,"wait",0,{}});}
};
static int failures=0;
#define CHECK(c,msg) do{if(!(c)){std::fprintf(stderr,"FAIL: %s\n",msg);++failures;}}while(0)

struct Device {
  MockQueue compute{"compute"},copy{"bcs-foreground"},maintenance{"bcs-maintenance"};
  p171::CopyQueueWork work;
  int compute_tail=0,copy_tail=0,recovered=0;
  std::vector<Ev> events;
  // record() mirrors SyclDevice::record -> ForegroundTails::record(id,is_copy).
  int issue_copy(void* d,const void* s,std::size_t n,std::vector<Ev> after) {
    return p171::foreground_copy(compute,copy,work,d,s,n,after,
      [this](Ev e,bool is_copy){events.push_back(e);(is_copy?copy_tail:compute_tail)=e.id;return e.id;},
      [this](Ev&){++recovered;});
  }
  int kernel() {auto e=compute.kernel();events.push_back(e);compute_tail=e.id;return e.id;}
  // Mirror of SyclDevice::fill: maintenance list only, never the copy route.
  int fill(void* d,const void* s,std::size_t n) {std::vector<Ev> after;return maintenance.memcpy(d,s,n,after).id;}
  void sync() {p171::foreground_sync(compute,copy,work);}
};

// One decode token as main.cpp issues it under overlap maintenance:
// kernels, asynchronous fills, 48 route-log D2H copies, then the 8-byte
// error/next-token readback ordered after the compute tail, then retirement sync.
static void token(Device& dev,int& fills_issued,std::vector<unsigned char>& host,std::vector<unsigned char>& device) {
  for(int k=0;k<6;++k)dev.kernel();
  for(int f=0;f<3;++f){dev.fill(device.data()+64+f,host.data()+f,1);++fills_issued;}
  for(int r=0;r<48;++r)dev.issue_copy(host.data()+128+r,device.data()+r,1,{dev.events.back()});
  dev.kernel();
  int tail=dev.compute_tail;
  dev.issue_copy(host.data(),device.data()+200,4,{dev.events.back()});
  dev.issue_copy(host.data()+4,device.data()+204,4,{dev.events.back()});
  (void)tail;dev.sync();
}

int main() {
  std::vector<unsigned char> host(512,0),device(512);for(int i=0;i<512;++i)device[i]=static_cast<unsigned char>(i*7+1);
  // ---- Candidate (B) view: compute-queue foreground copies.
  {
    ops.clear();Device dev;int fills=0;p171::compute_queue_copies=true;
    token(dev,fills,host,device);
    int bcs_foreground=0,barriers=0,maintenance_fills=0,copy_waits=0,compute_copies=0,last_kernel=-1;
    std::vector<int> readbacks;
    for(std::size_t i=0;i<ops.size();++i){const auto& o=ops[i];
      if(o.queue=="bcs-foreground"&&o.kind=="memcpy")++bcs_foreground;
      if(o.kind=="barrier")++barriers;
      if(o.queue=="bcs-maintenance"&&o.kind=="memcpy")++maintenance_fills;
      if(o.queue=="bcs-foreground"&&o.kind=="wait")++copy_waits;
      if(o.queue=="compute"&&o.kind=="kernel")last_kernel=int(i);
      if(o.queue=="compute"&&o.kind=="memcpy"){++compute_copies;readbacks.push_back(int(i));}
    }
    CHECK(bcs_foreground==0,"B: a foreground copy reached the BCS foreground list");
    CHECK(barriers==0,"B: a compute-queue barrier was submitted");
    CHECK(compute_copies==50,"B: expected 50 foreground copies on the in-order compute queue");
    CHECK(maintenance_fills==fills&&fills==3,"B: fills did not all reach the maintenance list");
    CHECK(readbacks.size()>=2&&readbacks[readbacks.size()-2]>last_kernel&&readbacks.back()>last_kernel,
          "B: token/error readback not ordered after the compute tail on the in-order queue");
    CHECK(copy_waits==0,"B: foreground_sync waited on an idle copy list");
    CHECK(dev.copy_tail==0&&dev.compute_tail==ops[readbacks.back()].event,"B: readback not recorded as the compute tail");
    CHECK(std::memcmp(host.data(),device.data()+200,8)==0,"B: readback bytes differ");
    CHECK(dev.recovered==0,"B: barrier recovery path used");
    CHECK(!dev.work.pending,"B: copy list marked as owning work");
  }
  // ---- Control (A) view: packet58as routing must be byte-for-byte unchanged.
  {
    ops.clear();Device dev;int fills=0;p171::compute_queue_copies=false;std::fill(host.begin(),host.end(),0);
    token(dev,fills,host,device);
    int bcs=0,barriers_after_copy=0,maintenance_fills=0,compute_copies=0;
    for(std::size_t i=0;i<ops.size();++i){const auto& o=ops[i];
      if(o.queue=="bcs-foreground"&&o.kind=="memcpy"){++bcs;if(i+1<ops.size()&&ops[i+1].queue=="compute"&&ops[i+1].kind=="barrier"&&ops[i+1].deps==std::vector<int>{o.event})++barriers_after_copy;}
      if(o.queue=="bcs-maintenance"&&o.kind=="memcpy")++maintenance_fills;
      if(o.queue=="compute"&&o.kind=="memcpy")++compute_copies;
    }
    CHECK(bcs==50&&barriers_after_copy==50&&compute_copies==0,"A: parent BCS copy + barrier routing changed");
    CHECK(maintenance_fills==3,"A: fills did not reach the maintenance list");
    CHECK(ops.size()>=2&&ops[ops.size()-2].queue=="bcs-foreground"&&ops[ops.size()-2].kind=="wait"&&ops.back().queue=="compute"&&ops.back().kind=="wait","A: parent two-queue sync changed");
    CHECK(std::memcmp(host.data(),device.data()+200,8)==0,"A: readback bytes differ");
  }
  // ---- Drained switch A->B: copy-list work issued earlier in the view is still waited once.
  {
    ops.clear();Device dev;p171::compute_queue_copies=false;dev.kernel();dev.issue_copy(host.data(),device.data(),4,{dev.events.back()});
    p171::compute_queue_copies=true;dev.sync();
    int copy_waits=0;for(auto& o:ops)copy_waits+=o.queue=="bcs-foreground"&&o.kind=="wait";
    CHECK(copy_waits==1,"switch: pending copy-list work not drained");
    ops.clear();dev.issue_copy(host.data(),device.data(),4,{dev.events.back()});dev.sync();
    copy_waits=0;for(auto& o:ops)copy_waits+=o.queue=="bcs-foreground"&&o.kind=="wait";
    CHECK(copy_waits==0,"switch: idle copy list waited after drain");
  }
  // ---- Barrier failure: recovery (1 ms proof loop in SyclDevice) only in copy-queue mode.
  {
    Device dev;dev.compute.fail_barrier=true;p171::compute_queue_copies=false;bool threw=false;
    try {dev.issue_copy(host.data(),device.data(),4,{});}catch(const std::runtime_error&){threw=true;}
    CHECK(threw&&dev.recovered==1,"A: barrier failure not recovered then rethrown");
    p171::compute_queue_copies=true;threw=false;
    try {dev.issue_copy(host.data(),device.data(),4,{});}catch(...){threw=true;}
    CHECK(!threw&&dev.recovered==1,"B: barrier path reached in compute-queue mode");
  }
  p171::compute_queue_copies=false;
  std::printf("{\"passed\":%s,\"failures\":%d}\n",failures?"false":"true",failures);
  return failures?1:0;
}
