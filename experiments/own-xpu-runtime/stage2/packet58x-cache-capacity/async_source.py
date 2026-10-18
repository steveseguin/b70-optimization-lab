"""Generate private owner/backend deltas; never write the frozen source trees."""
from pathlib import Path
from native_source import once, P, BASE


def support():
    out=P/'build/native'
    checked=BASE/'build/checked'/Path('experiments/own-xpu-runtime/stage2/packet58j-onecard-port')
    owner=(checked/'owner.cpp').read_text()
    owner='#include "'+str(P/'native/async_backend.hpp')+'"\n'+owner
    owner=once(owner,'events_.reserve(16384);fast_owners[this].bindings.reserve(4096);',
               'events_.reserve(16384);fast_owners[this].bindings.reserve(4096);p58v::register_owner(this,backend_.get());')
    owner=once(owner,'Device::~Device() {','Device::~Device() {\n  p58v::unregister_owner(this);')
    owner=once(owner,'return std::count_if(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);});',
               'return p58v::pending(*backend_)+std::count_if(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);});')
    owner += r'''
namespace p58v {
static std::map<ownrt::Device*,AsyncBackend*> owners;
void register_owner(ownrt::Device* d,ownrt::Backend* b){owners[d]=dynamic_cast<AsyncBackend*>(b);}
void unregister_owner(ownrt::Device* d){owners.erase(d);}
AsyncBackend* backend(ownrt::Device& d){return owners.at(&d);}
ownrt::Event copy(ownrt::Device& d,ownrt::Allocation dst,size_t off,ownrt::Allocation src,size_t soff,size_t n) {
  auto* b=backend(d);if(!b)throw std::logic_error("async cache backend unavailable");
  const auto& to=d.arena.row(dst);const auto& from=d.arena.row(src);
  if(!n||n>128ull*1024*1024||!to.live||!from.live||dst==src||
     to.memory!=ownrt::Memory::device||from.memory!=ownrt::Memory::pinned||
     off>to.bytes||n>to.bytes-off||soff>from.bytes||n>from.bytes-soff)
    throw std::logic_error("async fill extent/source/lifetime");
  return b->fill(static_cast<char*>(to.pointer)+off,static_cast<const char*>(from.pointer)+soff,n);
}
}
'''
    (out/'owner.cpp').write_text(owner)
    retire=(checked/'owner_retire.cpp').read_text()
    retire='#include <algorithm>\n#include "'+str(P/'native/async_backend.hpp')+'"\n'+retire
    retire=once(retire,'if (in_flight())','if (std::any_of(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);}))')
    retire=once(retire,'backend_->synchronize();','p58v::foreground_sync(*backend_);')
    (out/'owner_retire.cpp').write_text(retire)
    device=(checked/'single_device.cpp').read_text()
    device='#include "'+str(P/'native/async_backend.hpp')+'"\n'+device
    device=once(device,'class SyclDevice final : public Backend {','class SyclDevice final : public Backend, public p58v::AsyncBackend {')
    device=once(device,'  std::size_t card_;',r'''  std::unique_ptr<sycl::queue> maintenance_queue_;
  ze_command_list_handle_t maintenance_native_=nullptr;
  sycl::event fill_tail_;Event fill_ticket_=0;
  std::size_t card_;''')
    device=once(device,'      owned_cards.insert(card);',r'''      if(zeCommandListCreateImmediate(native_,native_device,&cd,&maintenance_native_)!=ZE_RESULT_SUCCESS)
        throw std::runtime_error("maintenance BCS immediate list failed");
      maintenance_queue_=std::make_unique<sycl::queue>(sycl::make_queue<sycl::backend::ext_oneapi_level_zero>(
        {maintenance_native_,d,sycl::ext::oneapi::level_zero::ownership::keep,properties},*context_,handler));
      owned_cards.insert(card);''')
    device=once(device,'} catch(...) {copy_queue_.reset();',
                '} catch(...) {maintenance_queue_.reset();if(maintenance_native_)zeCommandListDestroy(maintenance_native_);maintenance_native_=nullptr;copy_queue_.reset();')
    device=once(device,'  void synchronize() override {',r'''  Event fill(void* dst,const void* src,size_t bytes) override {
    check_error();
    // A second in-order BCS queue owns its own chain, never the compute tail.
    std::vector<sycl::event> after;if(fill_ticket_)after.push_back(fill_tail_);
    auto copied=maintenance_queue_->memcpy(dst,src,bytes,after);
    try {fill_tail_=copied;fill_ticket_=next_handle();return fill_ticket_;}
    catch(...) {hold_for_supervisor();}
  }
  bool fill_complete(Event ticket) override {
    check_error();if(!ticket||ticket!=fill_ticket_)throw std::logic_error("foreign maintenance ticket");
    return fill_tail_.get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;
  }
  size_t fills_pending() override {return fill_ticket_&&!fill_complete(fill_ticket_)?1:0;}
  void finish_fills() override {
    // Only shutdown / quiescent view transitions call this blocking operation.
    try {maintenance_queue_->wait();}catch(...){hold_for_supervisor();}
    maintenance_queue_->throw_asynchronous();check_error();
  }
  void foreground_sync() override {
    try {copy_queue_->wait();queue_->wait();}catch(...){hold_for_supervisor();}
    copy_queue_->throw_asynchronous();queue_->throw_asynchronous();check_error();
  }
  void synchronize() override {
    finish_fills();''')
    device=once(device,'void close_queue() override {copy_queue_.reset();',
        'void close_queue() override {maintenance_queue_.reset();fill_tail_=sycl::event{};fill_ticket_=0;'
        'if(maintenance_native_&&zeCommandListDestroy(maintenance_native_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("maintenance queue destroy failed");'
        'maintenance_native_=nullptr;copy_queue_.reset();')
    (out/'single_device.cpp').write_text(device)
    post=(checked/'postload_allocation_test.hpp').read_text().replace('18000000000ull','21552729600ull')
    post=once(post,'observer->allocation_calls-before==3','observer->allocation_calls-before==4')
    post=post.replace('postload_allocations\\\":3','postload_allocations\\\":4')
    post=once(post,'require(observer->backing_bytes<4*1024*1024',
              'require(arena.row(engine.publication_device).bytes==1179648,"bounded publication device staging");\n  require(observer->backing_bytes<4*1024*1024')
    (out/'postload_allocation_test.hpp').write_text(post)


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
