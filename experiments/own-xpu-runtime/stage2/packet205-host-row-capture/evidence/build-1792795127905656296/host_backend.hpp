#pragma once
#ifndef OWN_RT_HOST_ONLY
#error CPU fixture requires OWN_RT_HOST_ONLY
#endif
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/runtime_kernels.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/lifetime_mock.hpp"
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.hpp"
using integrated::HostOperation;
class Host final : public packet18::LifetimeMock {
public:
  ownrt::Event copy(void *a, const void *b, size_t n,
                    std::span<const ownrt::Event> d) override {
    auto e = LifetimeMock::copy(a, b, n, d);
    finish(e);
    return e;
  }
  std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const> p) override {
    auto host=std::dynamic_pointer_cast<const HostOperation>(op);if(!host)throw std::logic_error("host operation type");
    return [this,host,pointers=std::vector<void*>(p.begin(),p.end())]{host->run(pointers);return marker({});};
  }
  ownrt::Event compute(const ownrt::Operation &o, std::span<void *const> p,
                       std::span<const ownrt::Event> d) override {
    dynamic_cast<const HostOperation &>(o).run(p);
    return marker(d);
  }
};
