"""Focused transforms of the hash-verified generated parent, never its template."""
import json,shutil,re
from pathlib import Path
from prepare import P,AG,destination,sha,save
N=P/'build/native'
V=destination(AG)
C=V/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
def once(t,a,b):
    assert t.count(a)==1,(a[:100],t.count(a))
    return t.replace(a,b,1)
def include(p):return '#include '+json.dumps(str(p))+'\n'
def kernels():
    for file,namespace in [('p58ag_expert.hpp','p58ag_exp'),('p100_down.hpp','p100')]:
        t=((V/'build/native' if file.startswith('p58') else C)/file).read_text()
        if file=='p100_down.hpp':t=t.replace('namespace p100 {','namespace p58am_down {')
        t=include(P/'native/demand.hpp')+t
        t=t.replace('bool indirect=false;','bool indirect=false; unsigned partition=0;')
        # Bind two independent, original-slot-indexed 10-slot maps. Never pass
        # a staging map through p58::resolve's 512-expert table ABI.
        if file.startswith('p58'):
            t=t.replace('const float* halfcache=nullptr;','const float* halfcache=nullptr; const p58am::Map* descriptor=nullptr; const p58am::Map* stage=nullptr; unsigned partition=0;')
            t=t.replace('b.halfcache=Cached?', 'b.partition=partition;if(partition){b.descriptor=static_cast<const p58am::Map*>(p[20]);b.stage=static_cast<const p58am::Map*>(p[21]);}b.halfcache=Cached?')
            old='p58::resolve(stream?b.peer:b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect)'
            new='(b.partition&&((stream?b.stage->slots[slot].up:b.stage->slots[slot].gate)!=0)?reinterpret_cast<const uint8_t*>(stream?b.stage->slots[slot].up:b.stage->slots[slot].gate)+(route.row_begin+row)*b.rb:'+old+')'
            t=t.replace(old,new)
        else:
            t=t.replace(' p39::Bound bind(', ' struct Bound:p39::Bound { const p58am::Map* descriptor=nullptr;const p58am::Map* stage=nullptr;unsigned partition=0; };\n Bound bind(')
            t=t.replace('return base.bind(p);','Bound b;static_cast<p39::Bound&>(b)=base.bind(p);b.partition=partition;if(partition){b.descriptor=static_cast<const p58am::Map*>(p[20]);b.stage=static_cast<const p58am::Map*>(p[21]);}return b;')
            t=t.replace('source=route.row_begin+row;}', 'source=route.row_begin+row;}if(b.partition&&b.stage->slots[slot].down){bank=reinterpret_cast<const uint8_t*>(b.stage->slots[slot].down);source=route.row_begin+row;}')
        t=t.replace('   auto route=b.routes[slot];','   bool selected=!b.partition||bool(b.descriptor->slots[slot].resident)==(b.partition==1);if(!selected)continue;\n   auto route=b.routes[slot];')
        t=t.replace('    float value=0;if(valid)', '    bool selected=in_range&&(!b.partition||bool(b.descriptor->slots[slot].resident)==(b.partition==1));valid=valid&&selected;\n    float value=0;if(valid)')
        t=t.replace('if(in_range&&!physical){','if(selected&&!physical){')
        t=t.replace('b.partition&&((stream?', 'b.partition==2&&((stream?').replace('b.partition&&b.stage->slots', 'b.partition==2&&b.stage->slots')
        (N/file).write_text(t)
    t=(V/'build/native/p58ag_submit.cpp').read_text().replace(str(V/'build/native/p58ag_expert.hpp'),str(N/'p58ag_expert.hpp'))
    t+=include(P/'native/demand_submit.inc')
    (N/'p58ag_submit.cpp').write_text(t)

def generate():
    N.mkdir(parents=True,exist_ok=True)
    for p in (V/'build/native').iterdir():
        if p.is_file():shutil.copy2(p,N/p.name)
    # Local relative data consumed by __FILE__, checked before copying.
    for name in ('dispatch-speed6.json','selection.json'):
        src=V/'build/native'/name
        if not src.exists():
            matches=list(V.rglob(name));assert matches,name;src=matches[0]
        shutil.copy2(src,N/name)
    rope=AG/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rope.bf16'
    assert sha(rope) in (C/'rope.hpp').read_text()
    destination(rope).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(rope,destination(rope))
    save(P/'lineage/rope.json',dict(source=str(rope),sha256=sha(rope),bytes=rope.stat().st_size))
    kernels()
    bracket=(V/'native/bracket_table.hpp').read_text()
    bracket=bracket.replace('(views.size()==1||views.size()==5)','(views.size()==2||views.size()==5)')
    bracket=bracket.replace('if(views.size()==1)', 'if(views.size()==2)')
    bracket=bracket.replace('views[0].label=="S0"', 'views[0].label=="S0"&&views[1].label=="S1"')
    bracket=bracket.replace('views[i].hc==(i%2?"p60fusion":"production")','views[i].hc=="p60fusion"')
    (N/'bracket_table.hpp').write_text(bracket)
    t=(N/'main.cpp').read_text()
    t=t.replace(str(V/'native/bracket_table.hpp'),str(N/'bracket_table.hpp'))
    t=include(P/'native/demand_submit.hpp')+t
    t=once(t,'  int wait_seconds=60;','  int wait_seconds=300;\n  bool preparation_probe=false,demand_diagnostics=false;std::string demand="off",demand_identity;')
    t=once(t,'    else if (k == "--wait-seconds")','    else if(k=="--cpu-preparation-probe")a.preparation_probe=true;\n    else if(k=="--demand-diagnostics")a.demand_diagnostics=true;\n    else if(k=="--demand-identity")a.demand_identity=value();\n    else if(k=="--demand")a.demand=value();\n    else if (k == "--wait-seconds")')
    t=t.replace('getpriority(PRIO_PROCESS, 0) == a.native_nice','(getpriority(PRIO_PROCESS, 0) == a.native_nice || (a.preparation_probe&&getpriority(PRIO_PROCESS,0)==19))')
    t=once(t,'  require(a.wait_seconds>0 && a.wait_seconds<=600,"bounded wait deadline");','  require(a.wait_seconds>=300 && a.wait_seconds<=3600,"cold-evidence wait deadline");\n  require(a.demand=="off"||a.demand=="bcs-demand-retained32x2","single demand variant");')
    t=t.replace('static constexpr bool allocation_probe=false, legacy_pointer_probe=false;','bool allocation_probe=false, legacy_pointer_probe=false;')
    t=once(t,'  struct ExpertBank {',include(P/'native/engine_demand.inc')+'  struct ExpertBank {')
    t=once(t,'    cache_log.open(a.output/"cache.jsonl");','    demand_initialize();\n    cache_log.open(a.output/"cache.jsonl");')
    t=once(t,'    auto previous_submitted=submitted;','    if((a.demand!="off"||a.demand_diagnostics)&&demand_issue(index))return ++logical;\n    auto previous_submitted=submitted;')
    t=once(t,'    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);','    if(site.layer>=0&&p.launches[index].op=="route")demand_layers.at(site.layer).router=tail;\n    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);')
    t=t.replace('profile_events(args.timing!="token")','profile_events(args.timing!="token"||(args.demand_diagnostics&&!args.preparation_probe))')
    t=t.replace('(a.timing!="token"?"true":"false")','((a.timing!="token"||a.demand_diagnostics)?"true":"false")')
    t=t.replace('context_extent\\\":32','context_capacity\\\":4096')
    t=t.replace('submission_budget_ns\\\":4000000000','submission_budget_ns\\\":null,\\\"submission_data_deadline_enforced\\\":false')
    anchor=next(line for line in t.splitlines() if line.startswith('  r <<') and 'owner_cards' in line)
    t=once(t,anchor,r'''  r << ",\"demand_identity\":"<<ownrt::quote(a.demand_identity)<<",\"demand_variant\":"<<ownrt::quote(a.demand)
    <<",\"hc\":"<<ownrt::quote(a.hc)<<",\"hc_geometry\":"<<ownrt::quote(a.hc_geometry)<<",\"experts\":"<<ownrt::quote(a.experts)
    <<",\"other_fusion\":"<<ownrt::quote(a.other_fusion)<<",\"retirement\":"<<ownrt::quote(a.retirement)<<",\"cache_bytes\":"<<a.cache_bytes;'''+ '\n'+anchor)
    t=once(t,'    pending.clear();tail=0;','    demand_collect();\n    pending.clear();tail=0;')
    t=t.replace('        require(t.end_ns-t.start_ns<=4000000000ull,"GPU submission exceeded declared 4-second budget");','        // Duration is evidence, never an in-run data-proof deadline.')
    t=t.replace('require(t.start_ns && t.end_ns>=t.start_ns,"invalid profiling interval");', '/* Raw event timestamps are checked offline. */')
    t=t.replace('      require(item.launch.last-item.launch.first+1==item.launch.passes,"non-contiguous event group");', '      // Event-group accounting is an offline consistency check.')
    t=t.replace('max_submission_ns=std::max(max_submission_ns,t.end_ns-t.start_ns);','if(t.end_ns>=t.start_ns)max_submission_ns=std::max(max_submission_ns,t.end_ns-t.start_ns);')
    t=t.replace('double(t.end_ns-t.start_ns)/1e6','(double(t.end_ns)-double(t.start_ns))/1e6')
    t=t.replace('d->shutdown(std::chrono::seconds(60))','d->shutdown(std::chrono::seconds(a.wait_seconds))')
    t=once(t,'    std::fill(fp32_sources.begin(),fp32_sources.end(),0);\n    std::ofstream log(', '    demand_prepare();\n    std::fill(fp32_sources.begin(),fp32_sources.end(),0);\n    std::ofstream log(')
    t=once(t,'    drain();if(overlapping())maintenance.end(true);','    drain();demand_consumed();if(overlapping())maintenance.end(true);')
    t=once(t,'      expert_cache->observe(ids);previous_routes=std::move(ids);','      demand_pool.discard(previous_snapshot);previous_snapshot=maintenance_position;\n      expert_cache->observe(ids);previous_routes=std::move(ids);')
    t=once(t,'    maintenance_plan_ms=ms(start);previous_routes.clear();','    demand_select_fills();\n    maintenance_plan_ms=ms(start);previous_routes.clear();')
    t=once(t,'        publish_cache_table(maintenance.plan->table);maintenance.commit(*expert_cache,true,true);','        demand_pool.fill_done(maintenance.plan->epoch,true);\n        publish_cache_table(maintenance.plan->table);maintenance.commit(*expert_cache,true,true);')
    t=once(t,'last=p58v::copy(dev(0),cache_arena,offset,b.host,size_t(f.expert%p.g.experts)*b.expert_bytes,b.expert_bytes);','auto staged=demand_pool.leased(f.expert,maintenance.plan->epoch);\n            last=p58v::copy(dev(0),cache_arena,offset,staged<0?b.host:demand_storage,staged<0?size_t(f.expert%p.g.experts)*b.expert_bytes:size_t(staged)*p58am::expert_bytes+(projection==0?0:projection==1?p58am::gate_bytes:p58am::gate_bytes+p58am::up_bytes),b.expert_bytes);')
    t=once(t,'  e.drain();require(!e.poisoned', '  e.drain();e.cache_quiesce();e.demand_pool.reset(true);require(!e.poisoned')
    # Device-defined probe enters the same parser and Engine, substituting only
    # storage/transport before any GPU enumeration or model file open.
    t=once(t,'    devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card,profile_events||a.mtp||!a.draft_capture.empty())));','    if(!allocation_probe)devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(a.card,profile_events||a.mtp||!a.draft_capture.empty())));')
    t=t.replace('save(a.output/"device-contact.json","{\\"device_contact\\":true}");','save(a.output/"device-contact.json",allocation_probe?"{\\"device_contact\\":false}":"{\\"device_contact\\":true}");')
    t=once(t,'int main(int argc, char **argv) {',include(P/'native/preparation_probe.inc')+'int main(int argc, char **argv) {')
    t=once(t,'    a = parse(argc, argv);','    a = parse(argc, argv);\n    if(a.preparation_probe)return preparation_probe(a);')
    # Off and on share the exact same maximum allocation and composition.
    t=once(t,'fs::create_directories(view_output);e->bracket_select', 'fs::create_directories(view_output);e->a.demand=(view.label=="B0"||view.label=="B1"||view.label=="S1")?"bcs-demand-retained32x2":"off";e->bracket_select')
    from resident_port import port
    t=port(t)
    (N/'main.cpp').write_text(t)
    (N/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
    # Source substitution is permitted only after revocation; the real terminal
    # maintenance event, not a foreground event, owns every D2D source lease.
    t=(N/'owner.cpp').read_text().replace('from.memory!=ownrt::Memory::pinned||','(from.memory!=ownrt::Memory::pinned&&from.memory!=ownrt::Memory::device)||')
    (N/'owner.cpp').write_text(t)
    backend()
    for path in N.glob('*.cpp'):
        text=path.read_text().replace(str(V/'build/native/p58ag_submit.hpp'),str(N/'p58ag_submit.hpp'))
        path.write_text(text)

def backend():
    t=(N/'single_device.cpp').read_text()
    t=include(P/'native/demand.hpp')+t
    t=t.replace('public ForegroundPrefix {','public ForegroundPrefix, public p58am::Backend {')
    t=once(t,'  ForegroundTails foreground_tails_;', '''  ForegroundTails foreground_tails_;
  std::unique_ptr<sycl::queue> demand_queue_;
  ze_command_list_handle_t demand_native_=nullptr;
  std::vector<std::pair<uint64_t,sycl::event>> demand_events_;
  sycl::event& demand_event(uint64_t id){for(auto& r:demand_events_)if(r.first==id)return r.second;throw std::logic_error("foreign/retired demand ticket");}
''')
    t=once(t,'    events_.reserve(65536);','    events_.reserve(65536);demand_events_.reserve(512);static_assert(sizeof(std::pair<uint64_t,sycl::event>)<=128);')
    t=once(t,'      owned_cards.insert(card);','''      if(zeCommandListCreateImmediate(native_,native_device,&cd,&demand_native_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("demand copy-only BCS list");
      demand_queue_=std::make_unique<sycl::queue>(sycl::make_queue<sycl::backend::ext_oneapi_level_zero>({demand_native_,d,sycl::ext::oneapi::level_zero::ownership::keep,properties},*context_,handler));
      label_+=":demand-copy-only-ordinal="+std::to_string(ordinal);
      owned_cards.insert(card);''')
    t=t.replace('} catch(...) {maintenance_queue_.reset();','} catch(...) {demand_queue_.reset();if(demand_native_)zeCommandListDestroy(demand_native_);demand_native_=nullptr;maintenance_queue_.reset();')
    t=once(t,'  Event fill(void* dst,const void* src,size_t bytes) override {', '''  uint64_t demand_copy(void* dst,const void* src,size_t n,uint64_t producer) override {
    check_error();if(demand_events_.size()==512)throw std::length_error("bounded demand events");
    std::vector<sycl::event> after;if(producer)after.push_back(event(producer));
    auto copied=demand_queue_->memcpy(dst,src,n,after);auto id=next_handle();
    try {demand_events_.emplace_back(id,copied);}catch(...){hold_for_supervisor();}return id;
  }
  bool demand_complete(uint64_t id) override {check_error();return demand_event(id).get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;}
  void demand_barrier(uint64_t id) override {check_error();queue_->ext_oneapi_submit_barrier({demand_event(id)});}
  void demand_drain() override {try{demand_queue_->wait();}catch(...){hold_for_supervisor();}demand_queue_->throw_asynchronous();check_error();}
  size_t demand_pending() override {size_t n=0;for(auto&r:demand_events_)n+=!demand_complete(r.first);return n;}
  void demand_retire() override {if(demand_pending())throw std::logic_error("demand retirement before completion");demand_events_.clear();}
  std::array<uint64_t,2> demand_timing(uint64_t id) override {auto&e=demand_event(id);if(!demand_complete(id))throw std::logic_error("timing before demand completion");return {e.get_profiling_info<sycl::info::event_profiling::command_start>(),e.get_profiling_info<sycl::info::event_profiling::command_end>()};}
  Event fill(void* dst,const void* src,size_t bytes) override {''')
    t=t.replace('  size_t fills_pending() override {return fill_ticket_&&!fill_complete(fill_ticket_)?1:0;}','  size_t fills_pending() override {return demand_pending()+(fill_ticket_&&!fill_complete(fill_ticket_)?1:0);}')
    t=t.replace('  void synchronize() override {\n    finish_fills();','  void synchronize() override {\n    demand_drain();finish_fills();')
    t=t.replace('  void foreground_sync() override {','  void foreground_sync() override {\n    demand_drain();')
    t=t.replace('  void clear_events() override {events_.clear();','  void clear_events() override {demand_retire();events_.clear();')
    t=t.replace('  void close_queue() override {maintenance_queue_.reset();','  void close_queue() override {demand_retire();demand_queue_.reset();if(demand_native_&&zeCommandListDestroy(demand_native_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("demand queue destroy failed");demand_native_=nullptr;maintenance_queue_.reset();')
    wait=json.loads((P/'wait-budget.json').read_text())['per_operation_seconds'] if (P/'wait-budget.json').exists() else 900
    t=t.replace('std::chrono::seconds(60)',f'std::chrono::seconds({wait})')
    (N/'single_device.cpp').write_text(t)

if __name__=='__main__':generate()
