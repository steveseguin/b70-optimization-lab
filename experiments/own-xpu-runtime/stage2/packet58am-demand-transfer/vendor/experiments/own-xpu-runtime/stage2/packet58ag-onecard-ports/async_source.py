"""Generate private owner/backend deltas; never write the frozen source trees."""
from pathlib import Path
from native_source import once, P, BASE


def support():
    for name in ('owner.cpp','owner_retire.cpp','single_device.cpp','postload_allocation_test.hpp'):
        (P/'build/native'/name).write_bytes((P/'sources'/name).read_bytes())


def transform(text):
    old=next(line for line in text.splitlines() if line.startswith('#include ') and line.endswith('/cache_table.hpp"'))
    text=once(text,old,'#include "'+str(P/'native/cache_table.hpp')+'"')
    text='#include "'+str(P/'native/async_backend.hpp')+'"\n#include "'+str(P/'native/cache_protocol.hpp')+'"\n#include "'+str(P/'native/publish.hpp')+'"\n'+text
    old=next(line for line in text.splitlines() if line.startswith('#include ') and line.endswith('/postload_allocation_test.hpp"'))
    text=once(text,old,'#include "'+str(P/'build/native/postload_allocation_test.hpp')+'"')
    text=once(text,'uint64_t cache_bytes=18000000000ull;std::string miss_path="zero-copy";',
        'uint64_t cache_bytes=18000000000ull;std::string miss_path="zero-copy",cache_maintenance="serial";')
    text=once(text,'    if(k=="--cache-bytes")',
        '    if(k=="--cache-maintenance")a.cache_maintenance=value();\n    else if(k=="--cache-bytes")')
    text=once(text,'  require((a.mini||a.cache_bytes>=24000000ull)',
        '  require(a.cache_maintenance=="serial"||a.cache_maintenance=="overlap","cache maintenance mode");\n  require(a.cache_maintenance!="overlap"||a.miss_path=="zero-copy","overlap requires zero-copy misses");\n  require((a.mini||a.cache_bytes>=24000000ull)')
    text=once(text,'  std::ofstream cache_log;',r'''  std::ofstream cache_log;
  Allocation publication_device=0;
  p58v::Protocol maintenance;
  std::vector<uint32_t> previous_routes;
  uint64_t maintenance_position=0;
  double maintenance_plan_ms=0;
  uint64_t publication_uploads=0,publication_bytes=0;
  double publication_host_ms=0;
  bool overlapping()const{return a.cache_maintenance=="overlap";}
  void cache_quiesce() {
    if(!expert_cache||!overlapping())return;
    require(!maintenance.running,"cache switch during position");
    cache_boundary();
    if(maintenance.state==p58v::Protocol::State::filling) {
      auto* b=p58v::backend(dev(0));require(b,"missing maintenance backend");b->finish_fills();cache_boundary();
    }
    require(maintenance.state==p58v::Protocol::State::idle,"pending cache switch");previous_routes.clear();
  }
  void cache_mode(const std::string& mode) {
    require(mode=="serial"||mode=="overlap","unsupported cache mode");
    drain();cache_quiesce();a.cache_maintenance=mode;
    require(mode!="overlap"||a.miss_path=="zero-copy","overlap requires zero-copy");
  }
  void cache_boundary() {
    require(!maintenance.running,"cache publication during position");
    if(maintenance.state==p58v::Protocol::State::filling) {
      // Query once; a late fill is left unpublished, with safe host pointers.
      auto* b=p58v::backend(dev(0));require(b,"missing maintenance backend");
      if(!maintenance.ticket||b->fill_complete(maintenance.ticket)) {
        publish_cache_table(maintenance.plan->table);maintenance.commit(*expert_cache,true,true);
      }
    }
    if(maintenance.state==p58v::Protocol::State::planned) {
      auto safe=maintenance.revoked(*expert_cache);
      publish_cache_table(safe); // prior compute and host-pointer publication are complete
      ownrt::Event last=0;
      for(const auto& f:maintenance.plan->fills) {
        size_t offset=f.offset;
        for(int projection=0;projection<3;++projection)for(const auto& [name,b]:expert_banks)
          if(b.layer==int(f.expert/p.g.experts)&&b.projection==projection) {
            last=p58v::copy(dev(0),cache_arena,offset,b.host,size_t(f.expert%p.g.experts)*b.expert_bytes,b.expert_bytes);
            offset+=b.expert_bytes;
          }
        require(offset==f.offset+f.bytes,"async projection byte coverage");
      }
      cache_fill_bytes+=maintenance.plan->fill_bytes;cache_fills+=maintenance.plan->fills.size();
      maintenance.submitted(true,last);
    }
  }
  void cache_plan_during_position() {
    if(!expert_cache||!overlapping()||previous_routes.empty()||maintenance.state!=p58v::Protocol::State::idle)return;
    auto start=std::chrono::steady_clock::now();maintenance.prepare(*expert_cache,previous_routes);
    maintenance_plan_ms=ms(start);previous_routes.clear();
  }
''')
    # Keep the old 144-copy path as the serial control; same bounded staging allocation in both views.
    text=once(text,'  void publish_cache_table(const std::vector<p58::Entry>& table) {',
        '  void publish_cache_table(const std::vector<p58::Entry>& table) {\n    auto publication_start=std::chrono::steady_clock::now();')
    text=once(text,'    for(auto& [name,b]:expert_banks){\n      for(int id=0;id<p.g.experts;++id){',
        '    std::array<uint64_t*,144> destinations{};size_t table_index=0;\n    for(auto& [name,b]:expert_banks){\n      destinations[table_index++]=static_cast<uint64_t*>(dev(0).arena.row(b.table).pointer);\n      for(int id=0;id<p.g.experts;++id){')
    text=once(text,'      tail=copy.copy(b.table,0,table_staging,base*sizeof(p58::Pointer),p.g.experts*sizeof(p58::Pointer),{});base+=p.g.experts;',
        '      if(!overlapping())tail=copy.copy(b.table,0,table_staging,base*sizeof(p58::Pointer),p.g.experts*sizeof(p58::Pointer),{});base+=p.g.experts;')
    text=once(text,'    drain(); // pinned staging remains immutable until every publication completes',r'''    if(overlapping()) {
      require(dev(0).arena.row(table_staging).live&&dev(0).arena.row(table_staging).memory==Memory::pinned,"publication source lifetime");
      p58v::Publish op(destinations,p.g.experts*2,staging);
      std::vector<Allocation> ids{publication_device};for(const auto& [name,b]:expert_banks)ids.push_back(b.table);
      if(allocation_probe) {
        std::vector<ownrt::PreparedCompute> captured;dev(0).begin_capture(captured);
        try {dev(0).compute(op,ids,{});dev(0).end_capture();}catch(...){dev(0).end_capture();throw;}
      } else tail=dev(0).compute(op,ids,{});
    }
    drain(); // pinned staging remains immutable until every publication completes
    publication_uploads+=overlapping()?1:144;publication_bytes+=144*p.g.experts*sizeof(p58::Pointer);
    publication_host_ms+=ms(publication_start);''')
    text=once(text,'    publish_cache_table(expert_cache->table());',
        '    publication_device=allocate(0,"cache-publication-staging",144*p.g.experts*sizeof(p58::Pointer),Category::weights,Lifetime::process);\n    publish_cache_table(expert_cache->table());')
    text=once(text,'  void cache_begin_position(){if(expert_cache&&a.miss_path=="zero-copy")cache_epoch=expert_cache->begin_position();}',r'''  void cache_begin_position(){
    if(!expert_cache||a.miss_path!="zero-copy")return;
    ++maintenance_position;
    if(overlapping()){cache_boundary();maintenance.begin();}
    else cache_epoch=expert_cache->begin_position();
  }''')
    text=once(text,'    drain();expert_cache->finish_position(cache_epoch,true);ownrt::CopyEngine copy(dev(0));size_t n=p.g.top*sizeof(iq3::Route);',
        '    drain();if(overlapping())maintenance.end(true);else expert_cache->finish_position(cache_epoch,true);ownrt::CopyEngine copy(dev(0));size_t n=p.g.top*sizeof(iq3::Route);')
    text=once(text,'    fill_cache(ids);\n  }',r'''    if(overlapping()) {
      expert_cache->observe(ids);previous_routes=std::move(ids);
      cache_log<<"{\"position\":"<<maintenance_position<<",\"mode\":\"overlap\",\"plan_ms\":"<<maintenance_plan_ms
        <<",\"state\":"<<int(maintenance.state)<<",\"fill_bytes_total\":"<<cache_fill_bytes<<",\"fills_total\":"<<cache_fills
        <<",\"publication_uploads_total\":"<<publication_uploads<<",\"publication_bytes_total\":"<<publication_bytes
        <<",\"publication_host_ms_total\":"<<publication_host_ms<<"}\n";
      cache_log.flush();
      save(a.output/"cache-stats.json","{\"fill_bytes_total\":"+std::to_string(cache_fill_bytes)+",\"fills_total\":"+std::to_string(cache_fills)+",\"miss_path\":\"zero-copy\",\"mode\":\"overlap\"}\n");
    } else fill_cache(ids);
  }''')
    text=once(text,'      // One token-boundary readback contains sticky error and greedy output.',
        '      e->cache_plan_during_position(); // previous routes, current kernels already enqueued\n      // One token-boundary readback contains sticky error and greedy output.')
    # Account boundary publication in the token span, not before the timing start.
    text=once(text,'e->verify_configuration();e->cache_begin_position();','e->verify_configuration();')
    text=once(text,'      auto token_start=std::chrono::steady_clock::now();',
        '      auto token_start=std::chrono::steady_clock::now();e->cache_begin_position();')
    return text
