"""Packet176 native delta over the packet58as HEAD copy (path-rewritten only).

Copy-engine-free foreground token I/O (d2, extended to the token head).
Process-wide `--foreground-io copy|kernel` (default copy = packet58as); the
five-view bracket selects the same thread-local switch per view at the already
drained view boundary (A = spin, B = spin-kio).

B (kernel):
- Tail: one compute-queue kernel (p176::TailStore), enqueued after the last
  launch (argmax), stores error, next_token, a per-token stamp and the 48 route
  rows straight into the pinned host slab / pinned route log (USM host). The
  owner's existing compute drain (same spin policy, deadline, async-error and
  wait_and_throw path) is the only wait; the host then reads host memory. No
  copy command on any queue.
- Head: put() during the token head stages the token id and lookup rows in the
  pinned slab (offset 4096); one compute-queue kernel (p176::HeadLoad) loads
  them into the unchanged device buffers before the first launch, in queue
  order. No copy command on any queue, no host wait.
- Unchanged: fills (second BCS list), publication, every launch, arithmetic,
  selection, cache policy, spin policy, resident lookups, captures and the
  SyclDevice backend (no backend change).

Host-only additions in both arms: per-token head/tail/route-log transfer
times and the foreground transport label in timings.jsonl.

Every replacement is exact and counted; rerunning on changed text refuses.
"""
import sys
from pathlib import Path
P=Path(__file__).resolve().parent
N=P/'native'
INC='#include "'+str(N/'kernel_io.hpp')+'"\n'
FROZEN=str(P/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime')

HEADER=r'''#pragma once
// Packet176: process-wide copy-engine-free foreground token I/O
// (default copy = packet58as). Set only by the owner thread at a drained view
// boundary. Both operations are ordinary compute-queue kernels submitted
// through Device::compute (device-only bindings; the pinned host pointers are
// immutable kernel-argument values, as in p58v::Publish). Neither issues a
// memory-copy command, so no runtime copy offload can route them to a copy
// engine, and neither depends on any copy-engine event.
#include "@FROZEN@/stage2/packet58j-onecard-port/owner.hpp"
#include <array>
#include <cstdint>
#include <cstring>
#ifdef OWN_RT_HOST_ONLY
#include "@FROZEN@/stage2/packet58j-onecard-port/adapter.hpp"
#else
#include "@FROZEN@/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p176 {
inline thread_local bool kernel_io=false;
constexpr size_t tail_record_bytes=16;   // slab[0] + 0: status u32, token i32, stamp u64
constexpr size_t head_offset=4096;       // slab[0] + 4096: staged head bytes
constexpr size_t head_capacity=4*1024*1024-head_offset;
constexpr size_t max_head_items=8;
constexpr size_t max_route_layers=48;
// Bindings: p[0]=error, p[1]=next_token, p[2..2+layers)=route sources (device).
#ifdef OWN_RT_HOST_ONLY
struct TailStore final : integrated::HostOperation {
  uint8_t* host;uint8_t* routes;uint32_t layers,route_bytes;uint64_t stamp;
  TailStore(uint8_t* h,uint8_t* r,uint32_t l,uint32_t n,uint64_t s):host(h),routes(r),layers(l),route_bytes(n),stamp(s){}
  void run(std::span<void*const> p)const override {
    for(uint32_t i=0;i<layers;++i)std::memcpy(routes+size_t(i)*route_bytes,p[2+i],route_bytes);
    std::memcpy(host,p[0],4);std::memcpy(host+4,p[1],4);std::memcpy(host+8,&stamp,8);
  }
};
struct HeadLoad final : integrated::HostOperation {
  const uint8_t* host;std::array<uint32_t,max_head_items> offset{},bytes{};uint32_t items,total;
  HeadLoad(const uint8_t* h,std::array<uint32_t,max_head_items> o,std::array<uint32_t,max_head_items> b,uint32_t n,uint32_t t):host(h),offset(o),bytes(b),items(n),total(t){}
  void run(std::span<void*const> p)const override {
    for(uint32_t k=0;k<items;++k)std::memcpy(p[k],host+offset[k],bytes[k]);
  }
};
#else
struct TailStore final : ownrt::SyclOperation {
  uint8_t* host;uint8_t* routes;uint32_t layers,route_bytes;uint64_t stamp;
  TailStore(uint8_t* h,uint8_t* r,uint32_t l,uint32_t n,uint64_t s):host(h),routes(r),layers(l),route_bytes(n),stamp(s){}
  sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
    std::array<const uint8_t*,max_route_layers> source{};
    for(uint32_t i=0;i<layers;++i)source[i]=static_cast<const uint8_t*>(p[2+i]);
    auto* error=static_cast<const uint32_t*>(p[0]);auto* token=static_cast<const uint32_t*>(p[1]);
    auto* h=host;auto* r=routes;const size_t n=route_bytes,count=size_t(layers)*route_bytes;const uint64_t s=stamp;
    // One work-item per route byte plus one record item; all stores target
    // USM host memory and become host-visible when this kernel's event completes.
    return q.submit([&](sycl::handler& cgh){cgh.depends_on(deps);
      cgh.parallel_for(sycl::range<1>(count+1),[=](sycl::id<1> id){const size_t i=id[0];
        if(i==count){auto* w=reinterpret_cast<uint32_t*>(h);w[0]=error[0];w[1]=token[0];*reinterpret_cast<uint64_t*>(h+8)=s;}
        else r[i]=source[i/n][i%n];});});
  }
};
struct HeadLoad final : ownrt::SyclOperation {
  const uint8_t* host;std::array<uint32_t,max_head_items> offset{},bytes{};uint32_t items,total;
  HeadLoad(const uint8_t* h,std::array<uint32_t,max_head_items> o,std::array<uint32_t,max_head_items> b,uint32_t n,uint32_t t):host(h),offset(o),bytes(b),items(n),total(t){}
  sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
    std::array<uint8_t*,max_head_items> dest{};for(uint32_t k=0;k<items;++k)dest[k]=static_cast<uint8_t*>(p[k]);
    auto* h=host;auto o=offset;auto b=bytes;const uint32_t n=items;
    // Staged items are contiguous: item k covers [o[k], o[k]+b[k]) of the staging.
    return q.submit([&](sycl::handler& cgh){cgh.depends_on(deps);
      cgh.parallel_for(sycl::range<1>(total),[=](sycl::id<1> id){const uint32_t i=uint32_t(id[0]);uint32_t k=0;
        while(k+1<n&&i>=o[k+1])++k;dest[k][i-o[k]]=h[i];});});
  }
};
#endif
}
'''.replace('@FROZEN@',FROZEN)

def sub(path,old,new,count=1):
    text=path.read_text()
    assert text.count(old)==count,(str(path),old[:90],text.count(old))
    path.write_text(text.replace(old,new))

def main_cpp(path):
    first=path.read_text().splitlines(keepends=True)[0]
    assert first.endswith('/native/spin_wait.hpp"\n'),first
    sub(path,first,INC+first)
    # Options and CLI (process-wide; default copy = packet58as).
    sub(path,'  std::string wait_policy="poll"; bool wait_policy_supplied=false;\n',
             '  std::string wait_policy="poll"; bool wait_policy_supplied=false;\n  std::string foreground_io="copy"; bool foreground_io_supplied=false;\n')
    sub(path,'''    else if (k == "--wait-policy") {a.wait_policy=value();a.wait_policy_supplied=true;require(a.wait_policy=="poll"||a.wait_policy=="spin","wait policy dimension");}\n''',
'''    else if (k == "--wait-policy") {a.wait_policy=value();a.wait_policy_supplied=true;require(a.wait_policy=="poll"||a.wait_policy=="spin","wait policy dimension");}
    else if (k == "--foreground-io") {a.foreground_io=value();a.foreground_io_supplied=true;require(a.foreground_io=="copy"||a.foreground_io=="kernel","foreground io dimension");}
''')
    sub(path,'--wait-policy poll|spin (default:poll) --wait-seconds','--wait-policy poll|spin (default:poll) --foreground-io copy|kernel (default:copy) --wait-seconds')
    sub(path,'''",\\"wait_policy\\":"+ownrt::quote(parsed.wait_policy)+''','''",\\"wait_policy\\":"+ownrt::quote(parsed.wait_policy)+",\\"foreground_io\\":"+ownrt::quote(parsed.foreground_io)+''')
    sub(path,'''    require(!a.wait_policy_supplied||(a.draft_capture.empty()&&a.rank<0),"wait policy applies to single-owner request views");\n''',
'''    require(!a.wait_policy_supplied||(a.draft_capture.empty()&&a.rank<0),"wait policy applies to single-owner request views");
    require(!a.foreground_io_supplied||(a.draft_capture.empty()&&a.rank<0&&a.cards==1),"foreground io applies to single-owner one-card request views");
''')
    # Per-view switch at the drained view boundary; single-view runs use the CLI.
    sub(path,'''    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":view.hc=="spin";\n''',
'''    p58as::spin_enabled=a.bracket_inputs.empty()?a.wait_policy=="spin":(view.hc=="spin"||view.hc=="spin-kio");
    // p176: process-wide foreground token I/O, switched with the wait policy at
    // the already drained view boundary. Single-view (chain window) runs take
    // --foreground-io.
    p176::kernel_io=a.bracket_inputs.empty()?a.foreground_io=="kernel":view.hc=="spin-kio";
''')
    sub(path,'''",\\"wait_policy\\":"+ownrt::quote(view.hc)+''',
'''",\\"wait_policy\\":"+ownrt::quote(view.hc=="spin-kio"?std::string("spin"):view.hc)+",\\"bracket_arm\\":"+ownrt::quote(view.hc)+
        ",\\"foreground_io\\":"+ownrt::quote(std::string(p176::kernel_io?"kernel":"copy"))+''')
    # Engine state: head staging and tail stamp (host only).
    sub(path,'  uint64_t publication_uploads=0,publication_bytes=0;\n',
'''  uint64_t publication_uploads=0,publication_bytes=0;
  bool head_batch=false,tail_routes_written=false;size_t head_cursor=0;uint64_t io_stamp=0,kernel_head_loads=0,kernel_tail_stores=0;
  std::vector<std::pair<Allocation,uint32_t>> head_items;
  double route_log_ms=0;
''')
    # put(): during a kernel-io token head, stage instead of a BCS upload.
    sub(path,'''    require(n == s.n * flash::scalar_bytes(s.type), "control extent");
    upload(c, s.id, 0, b, n);
  }''','''    require(n == s.n * flash::scalar_bytes(s.type), "control extent");
    if(head_batch){stage_head(c,s.id,b,n);return;}
    upload(c, s.id, 0, b, n);
  }
  // p176 head: pinned staging + one compute-queue load kernel, no copy engine.
  void head_begin() {
    require(!head_batch&&head_items.empty(),"nested foreground head");
    drain(); // no kernel may still read the staging (same rule as upload)
    head_batch=true;head_cursor=0;
  }
  void stage_head(int c,Allocation dst,const void* src,size_t n) {
    require(c==0,"kernel foreground io is one-card");
    require(!bracket_weights_locked||dev(c).arena.row(dst).category!=Category::weights,"bracket immutable weight write refused");
    require(dev(c).arena.row(dst).memory==Memory::device&&dev(c).arena.row(dst).live,"head destination must be a live device allocation");
    require(head_items.size()<p176::max_head_items&&n>0&&head_cursor+n<=p176::head_capacity,"head staging bound");
    guard();auto started=std::chrono::steady_clock::now();
    std::memcpy(static_cast<uint8_t*>(dev(c).arena.row(slab[c]).pointer)+p176::head_offset+head_cursor,src,n);
    head_items.push_back({dst,uint32_t(n)});head_cursor+=n;transfer_ms+=ms(started);
  }
  void head_end() {
    require(head_batch,"foreground head not open");head_batch=false;
    if(head_items.empty())return;
    auto started=std::chrono::steady_clock::now();
    std::array<uint32_t,p176::max_head_items> offset{},bytes{};std::vector<Allocation> ids;uint32_t at=0;
    for(size_t k=0;k<head_items.size();++k){offset[k]=at;bytes[k]=head_items[k].second;at+=head_items[k].second;ids.push_back(head_items[k].first);}
    require(at==head_cursor,"head staging coverage");
    p176::HeadLoad op(static_cast<const uint8_t*>(dev(0).arena.row(slab[0]).pointer)+p176::head_offset,offset,bytes,uint32_t(head_items.size()),at);
    tail=dev(0).compute(op,ids,{});++kernel_head_loads;head_items.clear();head_cursor=0;
    transfer_ms+=ms(started);
  }
  // p176 tail: one compute-queue store kernel after the last launch.
  void tail_store() {
    auto* host=static_cast<uint8_t*>(dev(0).arena.row(slab[0]).pointer);
    const uint32_t poison=~0u;const int32_t none=-1;const uint64_t zero=0;++io_stamp;
    std::memcpy(host,&poison,4);std::memcpy(host+4,&none,4);std::memcpy(host+8,&zero,8);
    const bool routes=expert_cache&&a.miss_path=="zero-copy";
    std::vector<Allocation> ids{buffers[0].at("error").id,buffers[0].at("next_token").id};
    if(routes){require(route_sources.size()==p176::max_route_layers,"route census must cover every layer");for(const auto& source:route_sources)ids.push_back(source.second);}
    p176::TailStore op(host,routes?static_cast<uint8_t*>(dev(0).arena.row(route_log).pointer):nullptr,routes?uint32_t(route_sources.size()):0u,
      uint32_t(p.g.top*sizeof(iq3::Route)),io_stamp);
    tail=dev(0).compute(op,ids,{});++kernel_tail_stores;tail_routes_written=false;
  }
  void tail_check() {
    uint64_t stamp=0;std::memcpy(&stamp,static_cast<const uint8_t*>(dev(0).arena.row(slab[0]).pointer)+8,8);
    require(stamp==io_stamp,"kernel token store stamp mismatch");
    tail_routes_written=expert_cache&&a.miss_path=="zero-copy";
  }''')
    # cache_after_position: routes already stored by the tail kernel in B.
    sub(path,'''    drain();if(overlapping())maintenance.end(true);else expert_cache->finish_position(cache_epoch,true);ownrt::CopyEngine copy(dev(0));size_t n=p.g.top*sizeof(iq3::Route);
    for(size_t i=0;i<route_sources.size();++i)tail=copy.copy(route_log,i*n,route_sources[i].second,0,n,{});
    drain();std::vector<uint32_t> ids;''','''    drain();if(overlapping())maintenance.end(true);else expert_cache->finish_position(cache_epoch,true);size_t n=p.g.top*sizeof(iq3::Route);
    auto route_start=std::chrono::steady_clock::now();
    if(p176::kernel_io){require(tail_routes_written,"kernel route log missing for this position");tail_routes_written=false;}
    else {ownrt::CopyEngine copy(dev(0));
    for(size_t i=0;i<route_sources.size();++i)tail=copy.copy(route_log,i*n,route_sources[i].second,0,n,{});
    drain();}
    route_log_ms=ms(route_start);std::vector<uint32_t> ids;''')
    # Token loop: head.
    sub(path,'''      e->checkpoint("token-control-upload");
      for (int c=0;c<a.cards;++c)if(e->buffers[c].count("token"))e->put(c,"token",&token,4);''','''      e->checkpoint("token-control-upload");
      const bool kernel_io=p176::kernel_io;
      if(kernel_io){require(a.cards==1,"kernel foreground io is one-card");e->head_begin();}
      for (int c=0;c<a.cards;++c)if(e->buffers[c].count("token"))e->put(c,"token",&token,4);''')
    sub(path,'''      {auto t0=std::chrono::steady_clock::now();e->prepare_token(token);e->prepare_ms=Engine::ms(t0);}
      getrusage(RUSAGE_SELF,&prepare_after);''','''      {auto t0=std::chrono::steady_clock::now();e->prepare_token(token);e->prepare_ms=Engine::ms(t0);}
      if(kernel_io)e->head_end();
      const double head_transfer_ms=e->transfer_ms-token_t;e->route_log_ms=0;
      getrusage(RUSAGE_SELF,&prepare_after);''')
    # Token loop: tail.
    sub(path,'''      e->cache_plan_during_position(); // previous routes, current kernels already enqueued''','''      if(kernel_io)e->tail_store(); // compute queue, in order after the last launch
      e->cache_plan_during_position(); // previous routes, current kernels already enqueued''')
    sub(path,'''      auto& owner=e->dev(0);ownrt::CopyEngine copy(owner);
      auto start_transfer=std::chrono::steady_clock::now();
      e->tail=copy.copy(e->slab[0],0,e->buffers[0].at("error").id,0,4,{});
      e->tail=copy.copy(e->slab[0],4,e->buffers[0].at("next_token").id,0,4,{});
      e->drain();
      int status=0,result=-1;auto ptr=owner.arena.row(e->slab[0]).pointer;''','''      auto& owner=e->dev(0);
      auto start_transfer=std::chrono::steady_clock::now();const double tail_t0=e->transfer_ms;
      if(kernel_io)e->tail_check(); // stored by the drained compute-queue kernel
      else {ownrt::CopyEngine copy(owner);
      e->tail=copy.copy(e->slab[0],0,e->buffers[0].at("error").id,0,4,{});
      e->tail=copy.copy(e->slab[0],4,e->buffers[0].at("next_token").id,0,4,{});
      e->drain();}
      int status=0,result=-1;auto ptr=owner.arena.row(e->slab[0]).pointer;''')
    sub(path,'''      e->transfer_ms+=Engine::ms(start_transfer);
      require(!status,"sticky device error at token "+std::to_string(token_index)+"; rerun --checked for layer localization");''','''      e->transfer_ms+=Engine::ms(start_transfer);const double tail_transfer_ms=e->transfer_ms-tail_t0;
      require(!status,"sticky device error at token "+std::to_string(token_index)+"; rerun --checked for layer localization");''')
    sub(path,'''        <<",\\"transfer_wall_ms\\":"<<e->transfer_ms-token_t<<",\\"kernel_submissions\\":"<<e->submitted-token_sub''',
'''        <<",\\"transfer_wall_ms\\":"<<e->transfer_ms-token_t<<",\\"head_transfer_ms\\":"<<head_transfer_ms<<",\\"tail_transfer_ms\\":"<<tail_transfer_ms
        <<",\\"route_log_ms\\":"<<e->route_log_ms<<",\\"foreground_io\\":"<<(kernel_io?"\\"kernel\\"":"\\"copy\\"")<<",\\"kernel_submissions\\":"<<e->submitted-token_sub''')

def bracket_table(path):
    sub(path,'require(v.hc=="poll"||v.hc=="spin","lookup dimension");','require(v.hc=="spin"||v.hc=="spin-kio","foreground io dimension");')
    sub(path,'require(!a.wait_policy_supplied||a.wait_policy==v.hc,"wait policy conflicts with bracket view");',
             'require(!a.wait_policy_supplied||a.wait_policy=="spin","wait policy conflicts with bracket view");\n'
             '    require(!a.foreground_io_supplied,"bracket selects foreground io per view");')
    sub(path,'views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin"','views[0].label=="S0"&&views[0].capacity=="max"&&views[0].hc=="spin-kio"')
    sub(path,'views[i].hc==(i%2?"spin":"poll")','views[i].hc==(i%2?"spin-kio":"spin")')

def probe(path):
    # Real device-define CPU preparation: B views run the kernel head/tail with
    # the production plan's real buffers. The CPU transport executes no kernel,
    # so it emulates the two p176 operations byte-for-byte on backed memory.
    sub(path,'''  ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event> deps) override {++issued;return marker(deps);}''',
'''  size_t kernel_tail=0,kernel_head=0;
  ownrt::Event compute(const ownrt::Operation& op,std::span<void*const> p,std::span<const ownrt::Event> deps) override {
    auto fits=[&](const void* q,size_t n){for(auto [base,bytes]:backing){auto off=uintptr_t(q)-uintptr_t(base);if(off<=bytes&&n<=bytes-off)return true;}return false;};
    if(auto* t=dynamic_cast<const p176::TailStore*>(&op)) {
      require(p.size()==2+t->layers&&fits(p[0],4)&&fits(p[1],4)&&fits(t->host,16),"p176 tail bindings");
      for(uint32_t i=0;i<t->layers;++i){require(fits(p[2+i],t->route_bytes)&&fits(t->routes+size_t(i)*t->route_bytes,t->route_bytes),"p176 route bindings");std::memcpy(t->routes+size_t(i)*t->route_bytes,p[2+i],t->route_bytes);}
      std::memcpy(t->host,p[0],4);std::memcpy(t->host+4,p[1],4);std::memcpy(t->host+8,&t->stamp,8);++kernel_tail;
    } else if(auto* h=dynamic_cast<const p176::HeadLoad*>(&op)) {
      require(p.size()==h->items&&fits(h->host,h->total),"p176 head bindings");
      for(uint32_t k=0;k<h->items;++k){if(fits(p[k],h->bytes[k]))std::memcpy(p[k],h->host+h->offset[k],h->bytes[k]);}
      ++kernel_head;
    }
    ++issued;return marker(deps);
  }''')
    sub(path,'''      p58as::spin_enabled=view.hc=="spin";''','''      p58as::spin_enabled=view.hc=="spin"||view.hc=="spin-kio";p176::kernel_io=view.hc=="spin-kio";''')
    sub(path,'''        engine->cache_begin_position();engine->put(0,"token",&token,4);
        engine->prepare_token(token);
        for(const auto& l:engine->p.launches){auto& site=engine->issue_sites[&l-engine->p.launches.data()];if(!site.prefill_skip){engine->enqueue(l,engine->logical);++sites;}}
        engine->drain();engine->cache_after_position();''','''        engine->cache_begin_position();if(p176::kernel_io)engine->head_begin();engine->put(0,"token",&token,4);
        engine->prepare_token(token);if(p176::kernel_io)engine->head_end();
        for(const auto& l:engine->p.launches){auto& site=engine->issue_sites[&l-engine->p.launches.data()];if(!site.prefill_skip){engine->enqueue(l,engine->logical);++sites;}}
        if(p176::kernel_io)engine->tail_store();
        engine->drain();if(p176::kernel_io)engine->tail_check();engine->cache_after_position();''')
    sub(path,'''    require(transport->captured>1000&&transport->issued>1000&&sites>1000,"full production preparation coverage");''',
'''    require(transport->captured>1000&&transport->issued>1000&&sites>1000,"full production preparation coverage");
    require(transport->kernel_tail==24&&transport->kernel_head==24,"p176 kernel io in both B views");''')
    sub(path,'''+",\\"synthetic_weights\\":true''','''+",\\"p176_kernel_tail_stores\\":"+std::to_string(transport->kernel_tail)+",\\"p176_kernel_head_loads\\":"+std::to_string(transport->kernel_head)+",\\"synthetic_weights\\":true''')

if __name__=='__main__':
    assert '--apply' in sys.argv,'pass --apply once on the fresh copy'
    assert not (N/'kernel_io.hpp').exists(),'delta already applied'
    (N/'kernel_io.hpp').write_text(HEADER)
    main_cpp(N/'generated/main.cpp')
    bracket_table(N/'bracket_table.hpp')
    probe(N/'preparation_probe.cpp')
    print('applied packet176 native delta')
