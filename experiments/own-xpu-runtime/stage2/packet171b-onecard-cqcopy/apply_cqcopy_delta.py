"""Packet171b native delta over the packet58as HEAD copy (path-rewritten only).

Compute-queue foreground copies, switched per view at the drained boundary.
Every replacement is exact and counted; rerunning on changed text refuses.
Maintenance fills, publication, kernels, arithmetic, selection, cache policy,
spin policy and resident lookups are not touched.
"""
import sys
from pathlib import Path
P=Path(__file__).resolve().parent
N=P/'native'
INC='#include "'+str(N/'cq_copy.hpp')+'"\n'

def sub(path,old,new,count=1):
    text=path.read_text()
    assert text.count(old)==count,(str(path),old[:90],text.count(old))
    path.write_text(text.replace(old,new))

def single_device(path):
    first=path.read_text().splitlines(keepends=True)[0]
    assert first.endswith('/native/spin_wait.hpp"\n'),first
    sub(path,first,INC+first)
    sub(path,'  ForegroundTails foreground_tails_;\n','  ForegroundTails foreground_tails_;p171::CopyQueueWork copy_work_;\n')
    sub(path,
'''    auto copied=copy_queue_->memcpy(dst,src,n,after);
    // The compute queue must observe copy completion even for prepared kernels.
    // The returned owned copy event also protects pinned-source lifetime.
    try {queue_->ext_oneapi_submit_barrier({copied});return record(copied,true);}
    catch(...) {
      // DMA was submitted before the dependency barrier failed. It is not yet
      // in Device's event ledger: prove completion before rethrowing, otherwise
      // retain this owner and both allocations for the coordinator.
      auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(60);
      try {while(copied.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){
        if(std::chrono::steady_clock::now()>=deadline)hold_for_supervisor();std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }copied.wait();}catch(...){hold_for_supervisor();}
      throw;
    }
  }
''',
'''    // p171b: in compute-queue views one in-order compute memcpy is recorded as
    // the compute tail, with no barrier; its owned event and the existing drains
    // still prove pinned-source lifetime. Copy-queue views are packet58as:
    // the compute queue must observe copy completion even for prepared kernels.
    return p171::foreground_copy(*queue_,*copy_queue_,copy_work_,dst,src,n,after,
      [this](sycl::event e,bool is_copy){return record(std::move(e),is_copy);},
      [this](sycl::event& copied){
      // Copy-queue mode only. DMA was submitted before the dependency barrier
      // failed. It is not yet in Device's event ledger: prove completion before
      // rethrowing, otherwise retain this owner and both allocations.
      auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(60);
      try {while(copied.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){
        if(std::chrono::steady_clock::now()>=deadline)hold_for_supervisor();std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }copied.wait();}catch(...){hold_for_supervisor();}
    });
  }
''')
    sub(path,
'''  void foreground_sync() override {
    try {copy_queue_->wait();queue_->wait();}catch(...){hold_for_supervisor();}
''',
'''  void foreground_sync() override {
    // p171b: the copy list is waited only if it owns work issued in this view.
    try {p171::foreground_sync(*queue_,*copy_queue_,copy_work_);}catch(...){hold_for_supervisor();}
''')
    sub(path,
'''    try {copy_queue_->wait();queue_->wait();}catch(...){hold_for_supervisor();}
    copy_queue_->throw_asynchronous();queue_->throw_asynchronous();check_error();
  }
  void clear_events()''',
'''    try {copy_queue_->wait();queue_->wait();}catch(...){hold_for_supervisor();}
    copy_work_.pending=false;
    copy_queue_->throw_asynchronous();queue_->throw_asynchronous();check_error();
  }
  void clear_events()''')

def main_cpp(path):
    first=path.read_text().splitlines(keepends=True)[0]
    assert first.endswith('/native/spin_wait.hpp"\n'),first
    sub(path,first,INC+first)
    sub(path,
'''    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":view.hc=="spin";
''',
'''    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":(view.hc=="spin"||view.hc=="spin-cq");
    // p171b: owner-thread foreground-copy queue, switched with the wait policy at the
    // already drained view boundary; single-view runs keep packet58as copy-queue copies.
    p171::compute_queue_copies=!a.bracket_inputs.empty()&&view.hc=="spin-cq";
''')
    sub(path,
'''",\\"wait_policy\\":"+ownrt::quote(view.hc)+''',
'''",\\"wait_policy\\":"+ownrt::quote(view.hc=="spin-cq"?std::string("spin"):view.hc)+",\\"bracket_arm\\":"+ownrt::quote(view.hc)+
        ",\\"foreground_copies\\":"+ownrt::quote(std::string(p171::compute_queue_copies?"compute-queue":"copy-queue"))+''')

def bracket_table(path):
    sub(path,'require(v.hc=="poll"||v.hc=="spin","lookup dimension");','require(v.hc=="spin"||v.hc=="spin-cq","foreground copy dimension");')
    sub(path,'require(!a.wait_policy_supplied||a.wait_policy==v.hc,"wait policy conflicts with bracket view");',
             'require(!a.wait_policy_supplied||a.wait_policy=="spin","wait policy conflicts with bracket view");')
    sub(path,'views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin"','views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin-cq"')
    sub(path,'views[i].hc==(i%2?"spin":"poll")','views[i].hc==(i%2?"spin-cq":"spin")')

if __name__=='__main__':
    assert '--apply' in sys.argv,'pass --apply once on the fresh copy'
    single_device(N/'generated/single_device.cpp')
    main_cpp(N/'generated/main.cpp')
    bracket_table(N/'bracket_table.hpp')
    print('applied packet171b native delta')
