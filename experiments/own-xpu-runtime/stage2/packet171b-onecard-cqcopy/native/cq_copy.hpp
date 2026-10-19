#pragma once
#include <cstddef>
#include <utility>
#include <vector>
// Packet171b: queue placement of FOREGROUND copies only (token/error readback,
// token upload, route logs). Owner-thread policy, switched only at an already
// drained view boundary, in the same pattern as p58as::spin_enabled.
// Maintenance fills never pass through this header: they keep their own BCS
// immediate list (SyclDevice::fill, unchanged).
namespace p171 {
inline thread_local bool compute_queue_copies=false;
// True while the dedicated BCS foreground list owns work issued since its last
// host drain. Compute-queue copies never set it.
struct CopyQueueWork {bool pending=false;};
// Parent (packet58as): copy on the BCS list, then a compute-queue barrier so
// prepared kernels observe it; on barrier failure prove the DMA finished first.
// Candidate: one in-order compute-queue memcpy, owned event, no barrier.
// Returns the owned event and whether it is a copy-queue (BCS) tail.
template<class Queue,class Ev,class Record,class Recover>
auto foreground_copy(Queue& compute,Queue& copy,CopyQueueWork& work,void* dst,const void* src,std::size_t n,
                     const std::vector<Ev>& after,Record record,Recover recover) {
#ifndef P171_PARENT_ROUTING
  if(compute_queue_copies)return record(compute.memcpy(dst,src,n,after),false);
#endif
  auto copied=copy.memcpy(dst,src,n,after);work.pending=true;
  try {compute.ext_oneapi_submit_barrier(std::vector<Ev>{copied});return record(copied,true);}
  catch(...) {recover(copied);throw;}
}
// Parent: wait on the copy list, then the compute queue. Candidate: the compute
// queue only, unless the copy list owns work issued earlier in this view.
template<class Queue>
void foreground_sync(Queue& compute,Queue& copy,CopyQueueWork& work) {
#ifndef P171_PARENT_ROUTING
  if(compute_queue_copies&&!work.pending){compute.wait();return;}
#endif
  copy.wait();compute.wait();work.pending=false;
}
}
