#pragma once
#include "mock_device.hpp"
#include <cstdio>
#include <cstdlib>
#include <memory>

namespace packet18 {
// CPU model of context retention, independent of driver/USM implementations.
struct ContextOrder {
  bool native_released=false;
  size_t live=0, late_destructions=0;
  std::vector<std::string> order;
  void release_native() {native_released=true;order.push_back("native-context-release");}
  bool passed() const {return native_released && !live && !late_destructions;}
};
struct ContextReference {
  std::shared_ptr<ContextOrder> state;
  std::string kind;
  ContextReference(std::shared_ptr<ContextOrder> s,std::string k):state(std::move(s)),kind(std::move(k)) {
    if(state->native_released)throw std::logic_error("context borrower after native release");
    ++state->live;
  }
  ContextReference(const ContextReference&)=delete;
  ~ContextReference() {
    if(state->native_released)++state->late_destructions;
    --state->live;state->order.push_back("destroy:"+kind);
  }
};
class LifetimeMock : public ownrt::MockDevice {
  std::shared_ptr<ContextOrder> state=std::make_shared<ContextOrder>();
  std::shared_ptr<ContextReference> context=reference("context");
  std::array<std::shared_ptr<ContextReference>,2> queues{reference("queue0"),reference("queue1")};
  std::map<ownrt::Event,std::shared_ptr<ContextReference>> events;
  std::shared_ptr<ContextReference> reference(std::string kind) {
    return std::make_shared<ContextReference>(state,std::move(kind));
  }
public:
  auto canary_bundle() {return reference("kernel-bundle");}
  ownrt::Event copy(void* a,const void* b,size_t n,std::span<const ownrt::Event> deps) override {
    auto e=MockDevice::copy(a,b,n,deps);events.emplace(e,reference("event"));return e;
  }
  ownrt::Event marker(std::span<const ownrt::Event> deps) override {
    auto e=MockDevice::marker(deps);events.emplace(e,reference("event"));return e;
  }
  void clear_events() override {MockDevice::clear_events();events.clear();}
  void close_queue() override {MockDevice::close_queue();queues={};}
  void close_context() override {
    context.reset();
    if(state->live)throw std::logic_error("context borrowers survive native release boundary");
    MockDevice::close_context();state->release_native();
  }
  ~LifetimeMock() override {
    if(!state->passed()) {std::fputs("context lifetime FAILED\n",stderr);std::abort();}
    // Destruction itself is checked, after the native receipt may have been saved.
    std::fprintf(stderr,"context lifetime PASS: %zu destructions, native release last, zero late destructions\n",state->order.size()-1);
  }
};
}
