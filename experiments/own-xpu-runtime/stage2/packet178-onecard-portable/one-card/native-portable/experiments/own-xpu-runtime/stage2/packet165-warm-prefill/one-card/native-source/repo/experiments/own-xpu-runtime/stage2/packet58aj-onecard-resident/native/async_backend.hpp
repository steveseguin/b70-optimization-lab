#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
// Separate interface preserves the frozen Backend/Device ABI and kernel objects.
// Backend owns every maintenance event through final queue/context teardown.
namespace p58v {
struct AsyncBackend {
  virtual ~AsyncBackend() = default;
  virtual ownrt::Event fill(void*,const void*,size_t) = 0;
  virtual bool fill_complete(ownrt::Event) = 0;
  virtual size_t fills_pending() = 0;
  virtual void finish_fills() = 0;
  virtual void foreground_sync() = 0;
};
void register_owner(ownrt::Device*,ownrt::Backend*);
void unregister_owner(ownrt::Device*);
AsyncBackend* backend(ownrt::Device&);
ownrt::Event copy(ownrt::Device&,ownrt::Allocation,size_t,ownrt::Allocation,size_t,size_t);
inline size_t pending(ownrt::Backend& b) {
  auto* a=dynamic_cast<AsyncBackend*>(&b);
  try {return a?a->fills_pending():0;}catch(...){return 1;} // uncertainty retains ownership
}
inline void foreground_sync(ownrt::Backend& b) {
  if(auto* a=dynamic_cast<AsyncBackend*>(&b))a->foreground_sync();else b.synchronize();
}
}
