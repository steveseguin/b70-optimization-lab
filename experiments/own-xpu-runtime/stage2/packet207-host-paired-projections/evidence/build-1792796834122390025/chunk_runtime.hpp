#pragma once
// Included after the unchanged Engine and checkpoint helpers in the local overlay.
// No production/device path uses this experimental scheduling code.
#ifdef OWN_RT_HOST_ONLY
#include "paired_projection.hpp"
namespace p207 {
inline void record_state(Engine& e,const char* filename,size_t start,size_t count) {
    std::ofstream out(e.a.output/filename,std::ios::app);require(bool(out),"p207 trace open");
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
    out<<"}}\n";out.flush();require(bool(out),"p207 trace write");
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
  struct PairSite {
    int layer=0;std::string op;const flash::Launch* original=nullptr;
    std::array<Matrix,2> matrix;
    std::vector<ownrt::PreparedCompute> commands;
  };
  std::vector<PairSite> pairs;
  std::array<Allocation,2> pair_workspace{};
  const flash::Launch& site(const std::string& label)const {
    auto it=std::find_if(e.p.launches.begin(),e.p.launches.end(),[&](const auto& l){return l.label==label;});
    require(it!=e.p.launches.end(),"p207 required plan site "+label);return *it;
  }
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
    e.guard();require(!e.poisoned && !e.integer(0,"error") && e.integer(0,"active"),"p207 chunk guard");
    require(!e.bank_parity && !e.caching(),"p207 bank/cache admission");
  }
  void trace(size_t start) {record_state(e,"prefill-chunks.jsonl",start,2);}

public:
  explicit Chunks(Engine& engine):e(engine) {
    require(e.a.mini && e.a.pipeline_mini && e.a.memory=="resident" && !e.a.legacy && e.a.cards==1,"p207 constructor admission");
    // All row storage is allocated before ordinary/row prepared captures. There
    // is no release during this owner's request lifecycle.
    for(size_t row=0;row<2;++row) {
      banks[row].buffers=e.buffers[0];
      for(const auto& name:std::array<std::string,5>{"token","position","streams","embedding","blk.1.ple.lookup"}) {
        auto slot=e.buffers[0].at(name);auto bytes=slot.n*flash::scalar_bytes(slot.type);
        slot.id=e.allocate(0,"p207:row"+std::to_string(row)+":"+name,bytes,Category::scratch,Lifetime::transaction);
        std::vector<uint8_t> zero(bytes);e.upload(0,slot.id,0,zero.data(),zero.size());
        banks[row].buffers.at(name)=slot;
      }
      pair_workspace[row]=e.allocate(0,"p207:pair-workspace"+std::to_string(row),4,Category::scratch,Lifetime::transaction);
      // One reusable set across GDN layers, fixed into every row's captured
      // Matrix and prepared site. The other row cannot overwrite these values.
      const auto& first=site("blk.0.gdn.qkv");
      const std::array<std::string,4> originals{first.inputs.at(0),site("blk.0.hc.a.inject").outputs.at(0),first.outputs.at(0),site("blk.0.gdn.z").outputs.at(0)};
      for(size_t n=0;n<originals.size();++n) {
        auto value=e.buffers[0].at(originals[n]);size_t bytes=value.n*flash::scalar_bytes(value.type);
        value.id=e.allocate(0,"p207:row"+std::to_string(row)+":retained"+std::to_string(n),bytes,Category::scratch,Lifetime::transaction);
        std::vector<uint8_t> zero(bytes);e.upload(0,value.id,0,zero.data(),zero.size());
        for(int layer:{0,2}) {
          const auto prefix="blk."+std::to_string(layer)+".";const auto& qkv=site(prefix+"gdn.qkv");
          const std::array<std::string,4> names{qkv.inputs.at(0),site(prefix+"hc.a.inject").outputs.at(0),qkv.outputs.at(0),site(prefix+"gdn.z").outputs.at(0)};
          auto old=banks[row].buffers.at(names[n]);require(old.n==value.n && old.type==value.type,"p207 reused row extent");banks[row].buffers.at(names[n])=value;
        }
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
      require(e.issue_sites.size()==e.p.launches.size(),"p207 captured site count");
    }
    pairs.clear();
    for(int layer:{0,2})for(const auto* op:{"qkv","z"}) {
      PairSite pair;pair.layer=layer;pair.op=op;pair.original=&site("blk."+std::to_string(layer)+".gdn."+op);
      require(!e.small_followers.count(pair.original) && !e.small_groups.count(pair.original),"p207 original projection must be standalone");
      for(size_t row=0;row<2;++row) {
        pair.matrix[row]=banks[row].matrices.at(pair.original).at(0);pair.matrix[row].workspace=pair_workspace[row];
        require(pair.matrix[row].x==banks[row].buffers.at(pair.original->inputs.at(0)).id && pair.matrix[row].y==banks[row].buffers.at(pair.original->outputs.at(0)).id,"p207 row Matrix binding");
      }
      auto& d=e.dev(0);d.begin_capture(pair.commands);
      try{paired_projection(d,pair.matrix[0],pair.matrix[1],e.variant(*pair.original));d.end_capture();}
      catch(...){d.end_capture();throw;}
      require(pair.commands.size()==1 && pair.commands[0].ids.size()==7,"p207 one captured pair operation");pairs.push_back(std::move(pair));
    }
    captured_extent=e.context_extent;
  }
  void run(const std::vector<int>& input,size_t start) {
    require(!running && start+2<input.size() && start+2<=size_t(e.p.g.context) && start/32==(start+1)/32,"p207 two nonfinal rows/capacity");
    require(e.integer(0,"position")==int(start),"p207 canonical starting position");
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
      require(layers==std::vector<int>({0,1,2,3}),"p207 four-layer mini plan");
      std::vector<std::string> pair_records;size_t skipped=0;
      for(int layer:layers) {
        const auto prefix="blk."+std::to_string(layer)+".";
        const bool paired=layer==0 || layer==2;
        size_t qkv_index=paired?size_t(&site(prefix+"gdn.qkv")-e.p.launches.data()):0;
        size_t z_index=paired?size_t(&site(prefix+"gdn.z")-e.p.launches.data()):0;
        if(paired) {
          require(z_index==qkv_index+1 && site(prefix+"hc.a.inject").label==e.p.launches.at(qkv_index-1).label,"p207 exact projection split order");
          for(size_t row=0;row<2;++row) {
            e.guard();Scope selected(e,banks[row]);
            for(size_t i=0;i<qkv_index;++i)if(e.p.launches[i].label.starts_with(prefix))e.enqueue(e.p.launches[i],e.logical);
          }
          for(auto& pair:pairs)if(pair.layer==layer) {
            check();e.set_class(pair.original->label);e.last_site=&pair.original->label;
            auto event=e.dev(0).issue(pair.commands.at(0));e.finish(0,{event,event,1},true);++e.logical;
            std::ostringstream row;row<<"{\"start\":"<<start<<",\"layer\":"<<layer<<",\"op\":"<<ownrt::quote(pair.op)<<",\"captured\":true,\"issued\":true,\"skipped_original_sites\":2,\"weight_id\":"<<pair.matrix[0].w<<",\"input_ids\":["<<pair.matrix[0].x<<','<<pair.matrix[1].x<<"],\"output_ids\":["<<pair.matrix[0].y<<','<<pair.matrix[1].y<<"],\"workspace_ids\":["<<pair_workspace[0]<<','<<pair_workspace[1]<<"],\"inject_ids\":["<<banks[0].buffers.at(prefix+"hc.a.inject").id<<','<<banks[1].buffers.at(prefix+"hc.a.inject").id<<"]}";
            pair_records.push_back(row.str());
          }
        }
        for(size_t row=0;row<2;++row) {
          e.guard();Scope selected(e,banks[row]);
          for(size_t i=0;i<e.p.launches.size();++i) {
            const auto& launch=e.p.launches[i];if(!launch.label.starts_with(prefix))continue;
            if(paired && i<qkv_index)continue;
            if(paired && (i==qkv_index || i==z_index)){++skipped;continue;}
            e.enqueue(launch,e.logical);
          }
          if(e.a.p207_fail_after_row0 && layer==0 && row==0)throw std::runtime_error("p207 intentional partial chunk refusal");
        }
      }
      require(skipped==8 && pair_records.size()==4,"p207 exactly four pairs replace eight projections");
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
      require(native==std::array<int64_t,2>{final0,final1},"p207 native/staged history mismatch");
      e.fp32_sources[0]=0;e.fp32_extents[0]=0;check();trace(start);
      std::ofstream pair_log(e.a.output/"paired-sites.jsonl",std::ios::app);require(bool(pair_log),"p207 pair trace open");
      for(const auto& line:pair_records)pair_log<<line<<'\n';pair_log.flush();require(bool(pair_log),"p207 pair trace write");running=false;
    }catch(...) {
      e.history0=old0;e.history1=old1;e.poisoned=true;running=false;
      throw; // Never retry, publish a success, or run a serial fallback.
    }
  }
};
} // namespace p207
#endif
