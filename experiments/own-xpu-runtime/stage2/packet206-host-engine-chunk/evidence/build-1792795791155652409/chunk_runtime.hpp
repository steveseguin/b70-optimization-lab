#pragma once
// Included after the unchanged Engine and checkpoint helpers in the local overlay.
// No production/device path uses this experimental scheduling code.
#ifdef OWN_RT_HOST_ONLY
namespace p206 {
inline void record_state(Engine& e,const char* filename,size_t start,size_t count) {
    std::ofstream out(e.a.output/filename,std::ios::app);require(bool(out),"p206 trace open");
    size_t layers=0;for(const auto& site:e.issue_sites)if(site.layer_end)++layers;
    out<<"{\"passed\":true,\"start\":"<<start<<",\"count\":"<<count<<",\"context_extent\":"<<e.context_extent<<",\"layers\":"<<layers<<",\"published_position\":"<<start+count<<",\"canonical_state_sha256\":{";
    bool first=true;
    for(const auto& b:e.p.buffers) {
      if(!pipeline::checkpoint_rule(b.name).starts_with("saved"))continue;
      auto slot=e.buffers[0].at(b.name);size_t full=slot.n*flash::scalar_bytes(slot.type);
      size_t bytes=pipeline::checkpoint_slice_bytes(e,b.name,full,int64_t(start+count));
      auto value=e.readback(0,slot.id,bytes);
      out<<(first?"":",")<<ownrt::quote(b.name)<<':'<<ownrt::quote(hash(value));first=false;
    }
    out<<"}}\n";out.flush();require(bool(out),"p206 trace write");
  }
class Chunks {
  Engine& e;
  using BufferMap=decltype(Engine::buffers)::value_type;
  using MatrixMap=decltype(Engine::matrices);
  using PreparedMap=decltype(Engine::prepared);
  struct Bank {
    BufferMap buffers;
    MatrixMap matrices;
    PreparedMap prepared;
    std::vector<Engine::IssueSite> sites;
    int extent=32;
  };
  std::array<Bank,2> banks;
  int captured_extent=0;
  bool running=false;
  struct Scope {
    Engine& e;Bank& bank;
    void swap()noexcept {
      e.buffers[0].swap(bank.buffers);e.matrices.swap(bank.matrices);
      e.prepared.swap(bank.prepared);e.issue_sites.swap(bank.sites);
      std::swap(e.context_extent,bank.extent);
      e.fp32_sources[0]=0;e.fp32_extents[0]=0;
    }
    Scope(Engine& engine,Bank& b):e(engine),bank(b){swap();}
    ~Scope(){swap();}
  };
  void check() {
    e.guard();require(!e.poisoned && !e.integer(0,"error") && e.integer(0,"active"),"p206 chunk guard");
    require(!e.bank_parity && !e.caching(),"p206 bank/cache admission");
  }
  void trace(size_t start) {record_state(e,"prefill-chunks.jsonl",start,2);}

public:
  explicit Chunks(Engine& engine):e(engine) {
    require(e.a.mini && e.a.pipeline_mini && e.a.memory=="resident" && !e.a.legacy && e.a.cards==1,"p206 constructor admission");
    // All row storage is allocated before ordinary/row prepared captures. There
    // is no release during this owner's request lifecycle.
    for(size_t row=0;row<2;++row) {
      banks[row].buffers=e.buffers[0];
      for(const auto& name:std::array<std::string,5>{"token","position","streams","embedding","blk.1.ple.lookup"}) {
        auto slot=e.buffers[0].at(name);auto bytes=slot.n*flash::scalar_bytes(slot.type);
        slot.id=e.allocate(0,"p206:row"+std::to_string(row)+":"+name,bytes,Category::scratch,Lifetime::transaction);
        std::vector<uint8_t> zero(bytes);e.upload(0,slot.id,0,zero.data(),zero.size());
        banks[row].buffers.at(name)=slot;
      }
    }
  }
  void prepare() {
    e.drain();check();
    if(captured_extent==e.context_extent)return;
    for(auto& bank:banks) {
      bank.matrices.clear();bank.prepared.clear();bank.sites.clear();bank.extent=e.context_extent;
      Scope selected(e,bank);
      e.prepare_plan();e.prepare_commands();
      require(e.issue_sites.size()==e.p.launches.size(),"p206 captured site count");
    }
    captured_extent=e.context_extent;
  }
  void run(const std::vector<int>& input,size_t start) {
    require(!running && start+2<input.size() && start+2<=size_t(e.p.g.context) && start/32==(start+1)/32,"p206 two nonfinal rows/capacity");
    require(e.integer(0,"position")==int(start),"p206 canonical starting position");
    running=true;
    const int64_t old0=e.history0,old1=e.history1;
    int64_t final0=old0,final1=old1;
    try {
      e.drain();check();e.admit_position(int(start));prepare();
      // prepare_token performs real host lookup/upload. Each bank has its own
      // payload allocations. Temporarily advance the staging history only;
      // canonical host history remains old until the whole chunk succeeds.
      for(size_t row=0;row<2;++row) {
        Scope selected(e,banks[row]);int token=input.at(start+row);uint32_t position=uint32_t(start+row);
        e.put(0,"token",&token,4);e.put(0,"position",&position,4);e.prepare_token(token);
      }
      final0=e.history0;final1=e.history1;e.history0=old0;e.history1=old1;
      // Prefix includes begin and stream broadcast. Lookups are already staged.
      for(size_t row=0;row<2;++row) {
        Scope selected(e,banks[row]);
        for(const auto& launch:e.p.launches) {
          if(launch.label.starts_with("blk.") || launch.label.starts_with("final.") || launch.label=="logits" || launch.label=="argmax" || launch.op=="commit")continue;
          e.enqueue(launch,e.logical);
        }
      }
      std::vector<int> layers;
      for(const auto& launch:e.p.launches)if(launch.label.starts_with("blk.")) {
        int layer=std::stoi(launch.label.substr(4));if(layers.empty()||layers.back()!=layer)layers.push_back(layer);
      }
      require(layers==std::vector<int>({0,1,2,3}),"p206 four-layer mini plan");
      for(int layer:layers)for(size_t row=0;row<2;++row) {
        e.guard();Scope selected(e,banks[row]);
        for(const auto& launch:e.p.launches)if(launch.label.starts_with("blk."+std::to_string(layer)+"."))e.enqueue(launch,e.logical);
        if(e.a.p206_fail_after_row0 && layer==0 && row==0)throw std::runtime_error("p206 intentional partial chunk refusal");
      }
      e.drain();check();
      // No per-row commit touched canonical position. These copies are ordered,
      // not atomic: any refusal poisons the Engine and forbids checkpoint/retry.
      ownrt::CopyEngine copy(e.dev(0));
      for(const auto& name:std::array<std::string,2>{"streams","token"}) {
        auto dst=e.buffers[0].at(name),src=banks[1].buffers.at(name);
        e.tail=copy.copy(dst.id,0,src.id,0,dst.n*flash::scalar_bytes(dst.type),{});
      }
      e.drain();uint32_t position=uint32_t(start+2);e.put(0,"position",&position,4);e.drain();
      e.history0=final0;e.history1=final1;
      auto history=e.readback(0,e.buffers[0].at("token_history").id,16);std::array<int64_t,2> native{};std::memcpy(native.data(),history.data(),16);
      require(native==std::array<int64_t,2>{final0,final1},"p206 native/staged history mismatch");
      e.fp32_sources[0]=0;e.fp32_extents[0]=0;check();trace(start);running=false;
    }catch(...) {
      e.history0=old0;e.history1=old1;e.poisoned=true;running=false;
      throw; // Never retry, publish a success, or run a serial fallback.
    }
  }
};
} // namespace p206
#endif
