#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/ordered_queue.hpp"
#pragma once
// CPU-only transport seam. A null implementation queue is never submitted to:
// prepared_submit only stores its address; callbacks are represented by markers.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/prepared_submission.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#include <iostream>
#include <cstdlib>
namespace p151audit {
inline bool weight_allocation=false;
inline std::string site;
inline size_t prepared=0,issued=0,inherited=0;
template<class F> sycl::event bypass(F) {throw std::logic_error("native operation bypassed preparation at "+site);}
class Backend final:public ownrt::Backend, public ownrt::OrderedQueue {
 sycl::queue queue=sycl::detail::createSyclObjFromImpl<sycl::queue>(std::shared_ptr<sycl::detail::queue_impl>{});
public:
 bool ordered_prefix_complete(ownrt::Event) override {return true;}
 std::string identity()const override{return "CPU preparation audit; no device";}
 void* allocate(size_t n,ownrt::Memory)override {if(weight_allocation){static uintptr_t next=0x100000000000ull;auto p=reinterpret_cast<void*>(next);next+=(n+4095)&~size_t(4095);return p;}auto p=std::calloc(1,n);if(!p)throw std::bad_alloc();return p;}
 void release(void*p,ownrt::Memory)override {if(uintptr_t(p)<0x100000000000ull||uintptr_t(p)>=0x200000000000ull)std::free(p);}
 ownrt::Event copy(void*d,const void*s,size_t n,std::span<const ownrt::Event>)override {std::memcpy(d,s,n);return ownrt::next_handle();}
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 std::function<ownrt::Event()> prepare(const ownrt::Operation&op,std::span<void*const>p)override {
  ++prepared;return []{++issued;return ownrt::next_handle();};
 }
 ownrt::EventTiming timing(ownrt::Event e)override{return {e*2,e*2+1};} // synthetic marker interval, never a measurement
 bool complete(ownrt::Event)override{return true;}
 bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 void synchronize()override{} void clear_events()override{} void close_queue()override{} void close_context()override{}
};
}
