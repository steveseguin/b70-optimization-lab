"""Packet174 native delta over the packet58as HEAD copy (path-rewritten only).

Fill kick: right after a maintenance fill batch is submitted at the drained
position boundary, the owner issues one non-blocking host query of the
maintenance BCS immediate list (zeCommandListHostSynchronize, timeout 0) so
the driver hands the queued fills to the copy engine while the next position
computes. Process-wide `--fill-kick off|on` (default off = packet58as); the
five-view bracket selects the same thread-local switch per view at the already
drained view boundary (A = spin, B = spin-kick).

Unchanged: which experts are planned, filled, evicted and published, and when
(publication still happens only at a later drained boundary after a completed
fill), every kernel, arithmetic, selection, spin policy, resident lookups and
foreground copies. Host-only additions: kick counter, and per-position counts
of routed IDs served by published device pointers (hit readout), both logged
in cache.jsonl.

Every replacement is exact and counted; rerunning on changed text refuses.
"""
import sys
from pathlib import Path
P=Path(__file__).resolve().parent
N=P/'native'
INC='#include "'+str(N/'fill_kick.hpp')+'"\n'

def sub(path,old,new,count=1):
    text=path.read_text()
    assert text.count(old)==count,(str(path),old[:90],text.count(old))
    path.write_text(text.replace(old,new))

def single_device(path):
    first=path.read_text().splitlines(keepends=True)[0]
    assert first.endswith('/native/spin_wait.hpp"\n'),first
    sub(path,first,INC+first)
    sub(path,'class SyclDevice final : public Backend, public p58v::AsyncBackend, public ForegroundPrefix {\n',
             'class SyclDevice final : public Backend, public p58v::AsyncBackend, public ForegroundPrefix, public p174::FillKick {\n')
    sub(path,
'''  bool fill_complete(Event ticket) override {''',
'''  void kick_fills() override {
    check_error();
    // p174: one non-blocking query right after a fill batch, so the driver hands
    // the queued maintenance copies to the copy engine now. Never waits.
    auto r=zeCommandListHostSynchronize(maintenance_native_,0);
    if(r!=ZE_RESULT_SUCCESS&&r!=ZE_RESULT_NOT_READY)hold_for_supervisor();
  }
  bool fill_complete(Event ticket) override {''')

def main_cpp(path):
    first=path.read_text().splitlines(keepends=True)[0]
    assert first.endswith('/native/spin_wait.hpp"\n'),first
    sub(path,first,INC+first)
    # Options and CLI (process-wide; default off = packet58as).
    sub(path,'  std::string wait_policy="poll"; bool wait_policy_supplied=false;\n',
             '  std::string wait_policy="poll"; bool wait_policy_supplied=false;\n  std::string fill_kick="off"; bool fill_kick_supplied=false;\n')
    sub(path,'''    else if (k == "--wait-policy") {a.wait_policy=value();a.wait_policy_supplied=true;require(a.wait_policy=="poll"||a.wait_policy=="spin","wait policy dimension");}\n''',
'''    else if (k == "--wait-policy") {a.wait_policy=value();a.wait_policy_supplied=true;require(a.wait_policy=="poll"||a.wait_policy=="spin","wait policy dimension");}
    else if (k == "--fill-kick") {a.fill_kick=value();a.fill_kick_supplied=true;require(a.fill_kick=="off"||a.fill_kick=="on","fill kick dimension");}
''')
    sub(path,'--wait-policy poll|spin (default:poll) --wait-seconds','--wait-policy poll|spin (default:poll) --fill-kick off|on (default:off) --wait-seconds')
    sub(path,'''",\\"wait_policy\\":"+ownrt::quote(parsed.wait_policy)+''','''",\\"wait_policy\\":"+ownrt::quote(parsed.wait_policy)+",\\"fill_kick\\":"+ownrt::quote(parsed.fill_kick)+''')
    sub(path,'''    require(!a.wait_policy_supplied||(a.draft_capture.empty()&&a.rank<0),"wait policy applies to single-owner request views");\n''',
'''    require(!a.wait_policy_supplied||(a.draft_capture.empty()&&a.rank<0),"wait policy applies to single-owner request views");
    require(!a.fill_kick_supplied||(a.draft_capture.empty()&&a.rank<0),"fill kick applies to single-owner request views");
''')
    # Per-view switch at the drained view boundary; single-view runs use the CLI.
    sub(path,'''    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":view.hc=="spin";\n''',
'''    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":(view.hc=="spin"||view.hc=="spin-kick");
    // p174: process-wide fill kick, switched with the wait policy at the already
    // drained view boundary. Single-view (chain window) runs take --fill-kick.
    p174::fill_kick=a.bracket_inputs.empty()?a.fill_kick=="on":view.hc=="spin-kick";
''')
    sub(path,'''",\\"wait_policy\\":"+ownrt::quote(view.hc)+''',
'''",\\"wait_policy\\":"+ownrt::quote(view.hc=="spin-kick"?std::string("spin"):view.hc)+",\\"bracket_arm\\":"+ownrt::quote(view.hc)+
        ",\\"fill_kick\\":"+ownrt::quote(std::string(p174::fill_kick?"on":"off"))+''')
    # Engine counters.
    sub(path,'  uint64_t publication_uploads=0,publication_bytes=0;\n',
             '  uint64_t publication_uploads=0,publication_bytes=0;\n  uint64_t fill_kicks=0,route_hits=0,routes_seen=0;\n')
    # Kick once after a non-empty fill batch, after the ticket is owned.
    sub(path,'''      cache_fill_bytes+=maintenance.plan->fill_bytes;cache_fills+=maintenance.plan->fills.size();
      maintenance.submitted(true,last);
''','''      cache_fill_bytes+=maintenance.plan->fill_bytes;cache_fills+=maintenance.plan->fills.size();
      maintenance.submitted(true,last);
      if(p174::fill_kick&&!maintenance.plan->fills.empty())kick_fills();
''')
    sub(path,'''  void cache_plan_during_position() {''','''  void kick_fills() {
#ifdef OWN_RT_HOST_ONLY
    ++fill_kicks; // host fills are synchronous mock copies; the kick is a counted no-op
#else
    auto* kick=dynamic_cast<p174::FillKick*>(p58v::backend(dev(0)));require(kick,"fill kick backend");
    kick->kick_fills();++fill_kicks;
#endif
  }
  void cache_plan_during_position() {''')
    # Hit readout: routed IDs served by published device pointers this position.
    sub(path,'''    if(overlapping()) {
      expert_cache->observe(ids);previous_routes=std::move(ids);''','''    if(overlapping()) {
      for(auto id:ids)if(expert_cache->resident(id)&&!(maintenance.state==p58v::Protocol::State::filling&&maintenance.plan&&
        maintenance.plan->table.at(id).gate==expert_cache->experts().at(id).host_gate))++route_hits;
      routes_seen+=ids.size();
      expert_cache->observe(ids);previous_routes=std::move(ids);''')
    sub(path,'''        <<",\\"publication_host_ms_total\\":"<<publication_host_ms<<"}\\n";''',
'''        <<",\\"publication_host_ms_total\\":"<<publication_host_ms<<",\\"fill_kicks_total\\":"<<fill_kicks
        <<",\\"route_hits_total\\":"<<route_hits<<",\\"routes_total\\":"<<routes_seen<<"}\\n";''')

def bracket_table(path):
    sub(path,'require(v.hc=="poll"||v.hc=="spin","lookup dimension");','require(v.hc=="spin"||v.hc=="spin-kick","fill kick dimension");')
    sub(path,'require(!a.wait_policy_supplied||a.wait_policy==v.hc,"wait policy conflicts with bracket view");',
             'require(!a.wait_policy_supplied||a.wait_policy=="spin","wait policy conflicts with bracket view");\n'
             '    require(!a.fill_kick_supplied,"bracket selects the fill kick per view");')
    sub(path,'views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin"','views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin-kick"')
    sub(path,'views[i].hc==(i%2?"spin":"poll")','views[i].hc==(i%2?"spin-kick":"spin")')

if __name__=='__main__':
    assert '--apply' in sys.argv,'pass --apply once on the fresh copy'
    assert not (N/'fill_kick.hpp').exists(),'delta already applied'
    (N/'fill_kick.hpp').write_text('''#pragma once
// Packet174: process-wide maintenance fill kick (default off = packet58as).
// Set only by the owner thread at a drained view boundary.
namespace p174 {
inline thread_local bool fill_kick=false;
struct FillKick {
  virtual ~FillKick()=default;
  virtual void kick_fills()=0; // non-blocking; never waits for fill completion
};
}
''')
    single_device(N/'generated/single_device.cpp')
    main_cpp(N/'generated/main.cpp')
    bracket_table(N/'bracket_table.hpp')
    print('applied packet174 native delta')
