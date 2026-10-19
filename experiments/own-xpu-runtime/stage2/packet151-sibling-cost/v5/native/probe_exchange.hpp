#pragma once
// Serialized row-split communication envelope: original GEMVs still do all work.
// No arithmetic, weights, output, recurrent state or KV binding is replaced.
namespace p151 {
struct alignas(64) Box {uint32_t request,reply,input_bytes,output_bytes;};
static_assert(sizeof(Box)==64);
struct Exchange {
 Engine& e;uint8_t* shared;Box& box;uint8_t* payload;
 ownrt::Allocation scratch,staging;
 explicit Exchange(Engine& engine,uint8_t* bytes):e(engine),shared(bytes),
 box(*reinterpret_cast<Box*>(bytes+pipeline::probe_offset)),payload(bytes+pipeline::probe_offset+64) {
  require(e.p.g.h==2560,"p151 full model geometry");
  scratch=e.allocate(0,"p151:discard",65536,Category::runtime_overhead,Lifetime::process);
  staging=e.allocate(0,"p151:staging",65536,Category::runtime_overhead,Lifetime::process,Memory::pinned);
  e.probe_auxiliary.insert(scratch);e.probe_auxiliary.insert(staging);
  std::vector<uint8_t> zeros(65536);e.upload(0,scratch,0,zeros.data(),zeros.size());
 }
 void copy(ownrt::Allocation dst,ownrt::Allocation src,size_t n,size_t dst_offset=0) {
  // Same compute-queue CopyEngine and arena hazard events as head-split-compute.
  p105::CopyScope scope(false);ownrt::CopyEngine copy(e.dev(0));
  auto event=copy.copy(dst,dst_offset,src,0,n,{});e.wait(0,event);
 }
 void check() {
  pipeline_cancel_check();
  auto& peer=*reinterpret_cast<pipeline::native38::Mailbox*>(shared+2*pipeline::slot_bytes+256);
  require(!pipeline::native38::load(peer.abort),"p151 peer aborted");
 }
 void service() {
  using pipeline::native38::load;using pipeline::native38::publish;
  auto seq=load(box.request);if(seq==load(box.reply))return;
  check();require(e.a.rank==1&&e.sealed_selection.choices.at("probe")=="xchg","p151 service selection");
  const size_t n=box.input_bytes,m=box.output_bytes;
  require(n&&m&&n<=65536&&m<=65536,"p151 payload extent");
  std::memcpy(e.dev(0).arena.row(staging).pointer,payload,n);
  copy(scratch,staging,n); // queued behind the real draft's outstanding work
  copy(staging,scratch,m); // surrogate peer output; deliberately discarded
  std::memcpy(payload,e.dev(0).arena.row(staging).pointer,m);
  check();publish(box.reply,seq);
 }
 template<class Progress> void serve_correction(Progress progress) {
  // Explicit miss-only command. The ordinary hit worker does no probe polling.
  for(unsigned i=0;i<96;++i){
   require(p56x::wait([&]{return pipeline::native38::load(box.request)!=pipeline::native38::load(box.reply);},
     [&]{check();progress();},std::chrono::steady_clock::now()+std::chrono::seconds(e.a.seconds)),"p151 request timeout");
   service();
  }
 }
 void exchange(const flash::Launch& l) {
  using pipeline::native38::load;using pipeline::native38::publish;
  require(e.a.rank==0&&l.shape.size()==3&&l.shape[1]%2==0,"p151 row-split shape");
  const auto& input=e.buffers[0].at(l.inputs[0]);
  const size_t activation=input.n*flash::scalar_bytes(input.type);
  const size_t route_bytes=l.op!="gemv"?size_t(l.shape[0])*4:0;
  const size_t n=activation+route_bytes;
  size_t m=size_t(l.shape[0])*size_t(l.shape[1]/2)*2*(l.op=="expert_gate_up"?2:1)+4;
  // Coalesce projections sharing one input; the scalar GDN a/b remain local.
  if(ends(l.label,".gdn.z"))m+=e.buffers[0].at(l.label.substr(0,l.label.size()-1)+"qkv").n;
  if(ends(l.label,".qsa.ik")){
    const auto prefix=l.label.substr(0,l.label.size()-2);
    for(const char* suffix:{"qgate","k","v","iq"})m+=e.buffers[0].at(prefix+suffix).n;
  }
  require(input.type==flash::Scalar::bf16&&n&&m&&n<=65536&&m<=65536,"p151 BF16 payload bound");
  check();const uint32_t old=load(box.request);require(old==load(box.reply)&&old<UINT32_MAX,"p151 outstanding exchange");
  copy(staging,input.id,activation);
  if(route_bytes){
    auto ids=l.label.substr(0,l.label.find_last_of('.')+1)+"ids";
    const auto& routes=e.buffers[0].at(ids);
    require(routes.type==flash::Scalar::u32&&routes.n*4==route_bytes,"p151 expert ID payload");
    copy(staging,routes.id,route_bytes,activation);
  }
  std::memcpy(payload,e.dev(0).arena.row(staging).pointer,n);
  box.input_bytes=n;box.output_bytes=m;publish(box.request,old+1);
  require(p56x::wait([&]{return load(box.reply)==old+1;},[&]{check();},
    std::chrono::steady_clock::now()+std::chrono::seconds(e.a.seconds)),"p151 bounded exchange timeout");
  check();std::memcpy(e.dev(0).arena.row(staging).pointer,payload,m);copy(scratch,staging,m);
  ++e.correction_exchange_calls;e.correction_send_bytes+=n;e.correction_receive_bytes+=m;
 }
};
}
