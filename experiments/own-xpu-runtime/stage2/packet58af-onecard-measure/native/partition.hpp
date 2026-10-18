#pragma once
#include "measure.hpp"
namespace p58af {
inline thread_local int partition=0,site_layer=-1,site_projection=-1;
inline thread_local uintptr_t cache_begin=0,cache_end=0;
// Invalid routes belong to resident pass only, preserving status/error writes.
inline bool selected(int part,bool valid,uintptr_t address,uintptr_t begin,uintptr_t end){
  if(!part)return true;
  const bool resident=!valid||(address>=begin&&address<end);
  return part==(resident?1:2);
}
}
#ifndef OWN_RT_HOST_ONLY
// Include path supplied by the unchanged checked source before instantiation.
#include "../frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
namespace p58af {
template<class F>struct PartitionSubmission final:ownrt::PreparedSyclSubmission {
  sycl::queue* queue;F command;
  PartitionSubmission(sycl::queue& q,F f):queue(&q),command(std::move(f)){}
  std::function<ownrt::Event()> make_callback(ownrt::NativeIssueState state)const override {
    return [queue=queue,command=command,state]{
      {std::lock_guard lock(*state.mutex);if(*state.error)std::rethrow_exception(*state.error);}
      if(*state.allocation_card!=state.card)throw std::logic_error("partition card mismatch");
      const bool split=active()&&arm==2&&site_projection>=0&&site_layer==sample_layer;
      const unsigned count=split?2:1;
      if(state.events->size()+count>state.events->capacity())throw std::length_error("partition event capacity");
      ownrt::Event result=0;
      try {
        for(unsigned i=0;i<count;++i){
          partition=split?int(i+1):0;
          auto event=queue->submit(command);result=ownrt::next_handle();
          state.events->push_back({result,event,state.card});
          if(split)retain(event,site_layer,site_projection,int(i+1));
        }
        partition=0;return result;
      }catch(...){partition=0;throw;}
    };
  }
};
template<class F>sycl::event prepared_submit(sycl::queue& q,F command){
  if(!ownrt::submission_capture)return q.submit(std::move(command));
  if(*ownrt::submission_capture)throw std::logic_error("multiple partition submissions during capture");
  *ownrt::submission_capture=std::make_unique<PartitionSubmission<F>>(q,std::move(command));return {};
}
}
#endif
