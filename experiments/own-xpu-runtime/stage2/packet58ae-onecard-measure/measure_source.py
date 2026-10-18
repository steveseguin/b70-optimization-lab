"""Sparse boundary instrumentation. No new wait in a token, no tensor changes."""
import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
X=P.parent/'packet58x-cache-capacity'

def once(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a))
    return s.replace(a,b,1)

def generate():
    out=P/'build/native';out.mkdir(parents=True,exist_ok=True)
    snap=P/'lineage/snapshot'/X.relative_to(ROOT)
    s=(snap/'build/native/main.cpp').read_text().replace(str(X),str(P))
    s='#include "'+str(P/'native/measure.hpp')+'"\n'+s
    s=once(s,'  std::ofstream cache_log;', '  std::ofstream cache_log;\n  std::ofstream measure_log;\n  std::array<bool,24576> measure_host{};')
    s=once(s,'    auto publication_start=std::chrono::steady_clock::now();',
        '    auto publication_start=std::chrono::steady_clock::now();\n    const bool measured=p58ae::active();')
    s=once(s,'    if(overlapping()) {\n      require(dev(0).arena.row(table_staging)',
        '    if(measured)p58ae::pack_ms+=ms(publication_start);\n    if(overlapping()) {\n      require(dev(0).arena.row(table_staging)')
    s=once(s,'    drain(); // pinned staging remains immutable until every publication completes',
        '    auto measure_wait=measured?std::chrono::steady_clock::now():std::chrono::steady_clock::time_point{};\n    drain(); // pinned staging remains immutable until every publication completes\n    if(measured)p58ae::wait_ms+=ms(measure_wait);')
    s=once(s,'    publication_host_ms+=ms(publication_start);',
        '    publication_host_ms+=ms(publication_start);\n    if(measured){p58ae::boundary_ms+=ms(publication_start);++p58ae::publications;}\n    if(p58ae::arm)for(size_t i=0;i<table.size();++i)measure_host[i]=table[i].gate==expert_cache->experts()[i].host_gate;')
    # The route table already comes back once per position. No new D2H/readback.
    s=once(s,'      expert_cache->observe(ids);previous_routes=std::move(ids);',
        '''      if(p58ae::active())for(auto id:ids){const auto& e=expert_cache->experts()[id];auto& layer=p58ae::layers[id/p.g.experts];
        if(measure_host[id]){++layer.misses;layer.miss_bytes+=e.gate_bytes+e.up_bytes+e.down_bytes;}else{++layer.hits;layer.hit_bytes+=e.gate_bytes+e.up_bytes+e.down_bytes;}}
      expert_cache->observe(ids);previous_routes=std::move(ids);''')
    # Only two expert sites per layer; retain selected event objects before retire.
    s=once(s,'    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);',
        '''    if(p58ae::active()&&p58ae::arm==2&&(p.launches[index].op=="expert_gate_up"||p.launches[index].op=="routed_gemv")&&std::stoi(p.launches[index].label.substr(4))==p58ae::sample_layer) {
#ifndef OWN_RT_HOST_ONLY
      auto* measure=dynamic_cast<p58ae::Backend*>(p58v::backend(dev(c)));require(measure,"measurement backend");
      measure->retain(tail,std::stoi(p.launches[index].label.substr(4)),p.launches[index].op=="expert_gate_up"?0:1);
#endif
    }
    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);''')
    s=once(s,'      fs::create_directories(view_output);e->bracket_select(view.selection,view.digest);',
        '''      fs::create_directories(view_output);
      e->drain();e->cache_quiesce();p58ae::arm=view.label=="B0"?1:view.label=="B1"?2:0;
#ifndef OWN_RT_HOST_ONLY
      auto* measure=dynamic_cast<p58ae::Backend*>(p58v::backend(e->dev(0)));require(measure,"measurement backend");measure->profiling(p58ae::arm!=0);
#endif
      e->bracket_select(view.selection,view.digest);''')
    s=once(s,'    generated.clear();text.clear();',
        '    if(e->measure_log.is_open())e->measure_log.close();e->measure_log.open(output/"measure.jsonl");require(bool(e->measure_log),"measurement log");\n    generated.clear();text.clear();')
    s=once(s,'      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();',
        '      p58ae::begin(fixture_step);\n      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();')
    s=once(s,'      auto elapsed=Engine::ms(token_start);',
        '      p58ae::finish(e->measure_log,fixture_step,result,int(token_index));\n      auto elapsed=Engine::ms(token_start);')
    # No output writes in timed tokens: stream buffer is large enough for a request.
    s=once(s,'  std::ofstream measure_log;', '  std::array<char,2*1024*1024> measure_buffer{};\n  std::ofstream measure_log;')
    s=once(s,'e->measure_log.open(output/"measure.jsonl");', 'e->measure_log.rdbuf()->pubsetbuf(e->measure_buffer.data(),e->measure_buffer.size());e->measure_log.open(output/"measure.jsonl");')
    (out/'main.cpp').write_text(s)
    (out/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
    # Retain backend/owner source used by the parent; relink verification binds objects.
    receipt={}
    for name in ('single_device.cpp','owner.cpp','owner_retire.cpp','fullshape_submit_test.hpp','postload_allocation_test.hpp'):
        source=P/'lineage/supplemental'/name
        raw=source.read_bytes();receipt[str(source.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
        (out/name).write_text(raw.decode().replace(str(X),str(P)))
    d=(out/'single_device.cpp').read_text()
    d='#include "'+str(P/'native/measure.hpp')+'"\n'+d
    d=once(d,'public p58v::AsyncBackend {','public p58v::AsyncBackend, public p58ae::Backend {')
    d=once(d,'  void clear_events() override {events_.clear();}', '''  void profiling(bool enabled) override {
    synchronize();if(!events_.empty())throw std::logic_error("measurement switch requires retired events");
    auto handler=[this](sycl::exception_list errors){std::lock_guard lock(error_mutex_);if(!error_&&errors.size())error_=*errors.begin();};
    auto props=enabled?sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}:sycl::property_list{sycl::property::queue::in_order{}};
    // Preserve the queue object's address held by prepared callbacks. Every old
    // queue is drained before replacement; no context or USM allocation changes.
    *queue_=sycl::queue(*context_,queue_->get_device(),handler,props);
  }
  void retain(Event id,int layer,int projection) override {p58ae::retain(event(id),layer,projection);}
  void clear_events() override {events_.clear();}''')
    (out/'single_device.cpp').write_text(d)
    # Keep original arithmetic and original queue dependence. Only retain events.
    d=(snap/'native/publish.hpp').read_text().replace(str(X),str(P))
    d='#include "'+str(P/'native/measure.hpp')+'"\n'+d
    d=once(d,'    return q.submit([&](sycl::handler& h){h.depends_on(uploaded);',
        '    auto applied=q.submit([&](sycl::handler& h){h.depends_on(uploaded);')
    d=once(d,'dest[k/count][k%count]=data[k];});});',
        'dest[k/count][k%count]=data[k];});});\n    if(p58ae::active()){p58ae::retain(uploaded,-1,0);p58ae::retain(applied,-1,1);}\n    return applied;')
    (P/'native/publish.hpp').write_text(d)
    # Both arms plus controls in ONE load and a fixed 64-token request cap.
    d=(snap/'native/bracket_table.hpp').read_text().replace(str(X),str(P))
    d=d.replace('a.tokens==128,"128-token bracket required"','a.tokens==64,"64-token diagnostic bracket required"')
    d=d.replace('views[i].capacity==(i%2?"max":"18GB")','views[i].capacity=="max"')
    (P/'native/bracket_table.hpp').write_text(d)
    (P/'evidence/supplemental-source-copy.json').write_text(json.dumps(dict(files_sha256=receipt,device_executed=False),indent=2)+'\n')
    return out
if __name__=='__main__':generate()
