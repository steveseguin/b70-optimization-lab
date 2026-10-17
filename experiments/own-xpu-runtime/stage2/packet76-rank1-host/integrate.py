"""Apply scheduling-only changes to the new packet70 source copy."""
from pathlib import Path
import json
P=Path(__file__).resolve().parent
def edit(n,a,b):
 p=P/n;s=p.read_text();assert s.count(a)==1,(n,a,s.count(a));p.write_text(s.replace(a,b))
edit('owner_api.hpp','  void retire_completed_events();','  void retire_completed_events();\n  void retire_ordered_events(); // Packet76: explicit ordered-backend capability')
edit('single_device.cpp','#include "owner.hpp"','#include "owner.hpp"\n#include "ordered_queue.hpp"')
edit('single_device.cpp','class SyclDevice final : public Backend {','class SyclDevice final : public Backend, public OrderedQueue {')
edit('single_device.cpp','  bool complete(Event e) override {','  bool ordered_prefix_complete(Event e) override {\n    check_error();\n    if(!queue_->has_property<sycl::property::queue::in_order>())throw std::logic_error("ordered retirement requires in-order queue");\n    return complete(e);\n  }\n  bool complete(Event e) override {')
edit('owner_retire.cpp','#include "owner.hpp"','#include "owner.hpp"\n#include "ordered_queue.hpp"')
with (P/'owner_retire.cpp').open('a') as f:f.write('''
namespace ownrt {
void Device::retire_ordered_events() {
  if (quiescing_ || closed_ || !fault_.empty() || !graphs_.empty() || capture_)
    throw std::logic_error("ordered retirement requires an open eager owner");
  auto* ordered=dynamic_cast<OrderedQueue*>(backend_.get());
  if(!ordered)throw std::logic_error("backend has no ordered-prefix proof");
  try {
    if(!events_.empty() && !ordered->ordered_prefix_complete(events_.back()))
      throw std::logic_error("ordered event retirement with pending work");
    // Same error propagation and native cleanup as the original path. The
    // only elision is the redundant individual completion query for each
    // earlier event. No new work can enter this same-thread owner here.
    backend_->synchronize();
    backend_->clear_events();
    forget_event_queues(events_);
    events_.clear();
  } catch(const std::exception& e) {fault_=e.what();throw;}
}
}
''')
edit('p49d_submit.cpp','Submit resolve(std::string_view cls,std::string_view choice){','Submit resolve(std::string_view cls,std::string_view choice){\n if(cls=="host_retire"&&(choice=="production"||choice=="ordered"))return production;')
edit('p49d_submit.cpp','values.size()!=5','values.size()!=6')
edit('p49d_submit.cpp','target_values.erase("experts");','target_values.erase("experts");target_values.erase("host_retire");')
s=json.loads((P/'selection.json').read_text());s['decision']=None;s['choices']['host_retire']='production';(P/'selection.json').write_text(json.dumps(s,indent=2)+'\n')
edit('main.cpp','  p49d::Selection sealed_selection;','''  p49d::Selection sealed_selection;
  bool ordered_retirement=false;
  double retirement_ms=0,profiling_ms=0;
  uint64_t retirement_calls=0;
  void retire_events(int c) {
    auto started=std::chrono::steady_clock::now();
    if(ordered_retirement)dev(c).retire_ordered_events();
    else dev(c).retire_completed_events();
    retirement_ms+=ms(started);++retirement_calls;
  }''')
edit('main.cpp','    else require(a.selection_sha256.empty(),"selection SHA256 requires selection file");','''    else require(a.selection_sha256.empty(),"selection SHA256 requires selection file");
    ordered_retirement=a.rank==1 && sealed_selection.choices.contains("host_retire") && sealed_selection.choices.at("host_retire")=="ordered";''')
# Keep Host usable for small protocol tests. Its entire synchronous mock stream
# completes before returning; this does not enable a CPU model run in our gates.
edit('main.cpp','#include "host_spin.hpp"','#include "host_spin.hpp"\n#include "ordered_queue.hpp"')
edit('main.cpp','class Host final : public packet18::LifetimeMock {','class Host final : public packet18::LifetimeMock, public ownrt::OrderedQueue {')
edit('main.cpp','class Host final : public packet18::LifetimeMock, public ownrt::OrderedQueue {\npublic:','class Host final : public packet18::LifetimeMock, public ownrt::OrderedQueue {\npublic:\n  bool ordered_prefix_complete(ownrt::Event e) override {return complete(e);}')
edit('main.cpp','    if(!devices.empty())dev(0).retire_completed_events();','    if(!devices.empty())retire_events(0);')
s=(P/'main.cpp').read_text();assert s.count('dev(c).retire_completed_events();')==3
# Exclude the original fallback inside retire_events itself.
s=s.replace('      dev(c).retire_completed_events();','      retire_events(c);');(P/'main.cpp').write_text(s)
edit('main.cpp','    if(tail)wait(0,tail);\n#ifndef OWN_RT_HOST_ONLY','    if(tail)wait(0,tail);\n    auto profiling_start=std::chrono::steady_clock::now();\n#ifndef OWN_RT_HOST_ONLY')
edit('main.cpp','    pending.clear();attribution.events.clear();tail=0;','    profiling_ms+=ms(profiling_start);\n    pending.clear();attribution.events.clear();tail=0;')
edit('rank.hpp',' auto waits=e.host_waits;double waited=e.wait_ms;e.family_ms.fill(0);',' auto waits=e.host_waits;double waited=e.wait_ms;e.family_ms.fill(0);\n const auto retire_calls=e.retirement_calls;const double retire_ms=e.retirement_ms,profile_ms=e.profiling_ms;')
edit('rank.hpp','  <<",\\"launch_extent\\":"','  <<",\\"p76_retirement_ms\\":"<<e.retirement_ms-retire_ms<<",\\"p76_retirement_calls\\":"<<e.retirement_calls-retire_calls<<",\\"p76_profiling_ms\\":"<<e.profiling_ms-profile_ms<<",\\"p76_ordered_retirement\\":"<<(e.ordered_retirement?"true":"false")\n  <<",\\"launch_extent\\":"')
