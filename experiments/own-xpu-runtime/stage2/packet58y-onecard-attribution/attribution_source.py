"""Focused non-synchronizing instrumentation on the copied packet58v engine."""
from native_source import once,P

def transform(text):
    text='#include "'+str(P/'native/attribution.hpp')+'"\n'+text
    text=once(text,'  std::ofstream cache_log;', '  std::ofstream cache_log;\n  std::ofstream attribution_log;\n  std::array<bool,24576> published_host{};')
    text=once(text,'  std::string nongemv =', '  bool attribution=false;\n  std::string nongemv =')
    text=once(text,'    else if (k == "--timing")', '    else if (k == "--attribution") {require(value()=="host","host-only attribution required");a.attribution=true;}\n    else if (k == "--timing")')
    text=once(text,'  require(a.timing=="token"', '  require(!a.attribution||a.timing=="token","attribution must preserve unprofiled queues");\n  require(a.timing=="token"')
    text=once(text,'  void wait(int c, ownrt::Event e) {','  void wait(int c, ownrt::Event e) {\n    p58y::Waiting attributed_wait;')
    text=once(text,'  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {',
      '  void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {\n    p58y::Reason reason(p58y::input_upload);')
    text=once(text,'  void publish_cache_table(const std::vector<p58::Entry>& table) {',
      '  void publish_cache_table(const std::vector<p58::Entry>& table) {\n    p58y::Reason reason(p58y::table_publication);')
    text=once(text,'    publication_host_ms+=ms(publication_start);', '''    publication_host_ms+=ms(publication_start);
    if(a.attribution) {
      // Track the table actually published, including revoked victims and fills
      // that have not completed. Cache::resident alone is stale in this window.
      for(size_t i=0;i<table.size();++i)published_host[i]=table[i].gate==expert_cache->experts()[i].host_gate;
      if(p58y::stats.active){++p58y::stats.publications;p58y::stats.publication_bytes+=144*p.g.experts*sizeof(p58::Pointer);}
    }''')
    text=once(text,'      cache_fill_bytes+=maintenance.plan->fill_bytes;cache_fills+=maintenance.plan->fills.size();',
      '''      if(p58y::stats.active){p58y::stats.fill_bytes+=maintenance.plan->fill_bytes;p58y::stats.fills+=maintenance.plan->fills.size();}
      cache_fill_bytes+=maintenance.plan->fill_bytes;cache_fills+=maintenance.plan->fills.size();''')
    text=once(text,'      if(!maintenance.ticket||b->fill_complete(maintenance.ticket)) {',
      '''      const bool completed=!maintenance.ticket||b->fill_complete(maintenance.ticket);
      if(p58y::stats.active){++p58y::stats.fill_queries;p58y::stats.fill_pending_queries+=!completed;}
      if(completed) {''')
    text=once(text,'    auto start=std::chrono::steady_clock::now();maintenance.prepare',
      '    p58y::Scope phase(p58y::cache_plan);\n    auto start=std::chrono::steady_clock::now();maintenance.prepare')
    text=once(text,'    drain();if(overlapping())maintenance.end(true);',
      '    p58y::Scope phase(p58y::cache_after);\n    p58y::Reason reason(p58y::readback);\n    drain();if(overlapping())maintenance.end(true);')
    text=once(text,'      expert_cache->observe(ids);previous_routes=std::move(ids);',
      '''      if(p58y::stats.active)for(auto id:ids){const auto& e=expert_cache->experts()[id];const auto n=e.gate_bytes+e.up_bytes+e.down_bytes;
        if(published_host[id]){++p58y::stats.misses;p58y::stats.miss_bytes+=n;}else{++p58y::stats.hits;p58y::stats.hit_bytes+=n;}}
      expert_cache->observe(ids);previous_routes=std::move(ids);''')
    text=once(text,'auto started=class_timing?std::chrono::steady_clock::now()',
      'auto started=(class_timing||p58y::stats.active)?std::chrono::steady_clock::now()')
    text=once(text,'    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);',
      '''    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);
    if(p58y::stats.active){p58y::stats.enqueue_class_ms[site.family]+=ms(started)-(wait_ms-waited);p58y::stats.class_submissions[site.family]+=submitted-previous_submitted;}''')
    text=once(text,'    generated.clear();text.clear();',
      '''    if(a.attribution){if(e->attribution_log.is_open())e->attribution_log.close();e->attribution_log.open(output/"attribution.jsonl");require(bool(e->attribution_log),"attribution output");}
    generated.clear();text.clear();''')
    text=once(text,'      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();',
      '''      p58y::begin(a.attribution);
      auto token_start=std::chrono::steady_clock::now();{p58y::Scope phase(p58y::cache_boundary);e->cache_begin_position();}''')
    text=once(text,'      for (int c=0;c<a.cards;++c)if(e->buffers[c].count("token"))',
      '      p58y::switch_phase(p58y::prepare);\n      for (int c=0;c<a.cards;++c)if(e->buffers[c].count("token"))')
    text=once(text,'      auto enqueue_start=std::chrono::steady_clock::now();',
      '      p58y::switch_phase(p58y::enqueue);\n      auto enqueue_start=std::chrono::steady_clock::now();')
    text=once(text,'      e->cache_plan_during_position();',
      '      p58y::switch_phase(p58y::other);\n      e->cache_plan_during_position();')
    text=once(text,'      auto& owner=e->dev(0);ownrt::CopyEngine copy(owner);',
      '''      p58y::switch_phase(p58y::readbacks);
      p58y::Reason readback_reason(p58y::readback);
      auto& owner=e->dev(0);ownrt::CopyEngine copy(owner);''')
    text=once(text,'      e->cache_after_position();',
      '      p58y::switch_phase(p58y::other);\n      e->cache_after_position();')
    text=once(text,'      auto elapsed=Engine::ms(token_start);',
      '''      p58y::finish(e->attribution_log,fixture_step,result,int(token_index),e->maintenance.state==p58v::Protocol::State::filling);
      auto elapsed=Engine::ms(token_start);''')
    return text

def support():
    path=P/'build/native/single_device.cpp'
    t='#include "'+str(P/'native/attribution.hpp')+'"\n'+path.read_text()
    t=once(t,'  void foreground_sync() override {',
      '  void foreground_sync() override {\n    p58y::Waiting attributed_existing_queue_wait;')
    t=once(t,'  void finish_fills() override {',
      '  void finish_fills() override {\n    p58y::Reason reason(p58y::fill_copies);p58y::Waiting attributed_existing_fill_wait;')
    path.write_text(t)
