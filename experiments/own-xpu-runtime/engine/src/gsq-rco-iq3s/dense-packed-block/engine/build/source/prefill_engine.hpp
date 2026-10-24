// Included inside the Engine definition, after generic_engine.hpp.
//
// Batched prefill: run a chunk of M prompt rows through this rank's plan, launch by launch (layer-major).
// - Linear sites run ONCE for all M rows (gsq_linear_matrix with m.tokens=M dense rows, or M*top routed
//   slots). Kernels reuse each weight row across the rows; each row keeps its single-row arithmetic.
// - Every other site is the unchanged single-row operation replayed for rows 0..M-1 through device row
//   views (ownrt::Device::row_views). Intermediate buffers map to row r of an M-row shadow, `position` and
//   `token` map to per-row arrays, and recurrent banks alternate by row parity, exactly as M consecutive
//   single-row steps with a bank swap after each would. Persistent state (KV, pooled/raw keys, recurrent
//   state and histories, token history) is shared, so row r sees rows < r.
// - Each QSA select/attention row is prepared with the context extent that its single-row step admits.
// The decode path is untouched: prepared commands are never redirected, and with prefill_rows == 0 nothing
// here allocates or runs.
struct PrefillShadow {Allocation id=0;size_t row_bytes=0;};
std::map<std::string,PrefillShadow> prefill_shadows;   // by role: "blk.*.<suffix>" for layer buffers
std::map<std::string,std::string> prefill_role_of;     // plan buffer name -> role
std::vector<const flash::Launch*> prefill_sites;
Allocation prefill_positions=0,prefill_tokens=0;
uint64_t prefill_chunks=0,prefill_rows_done=0;
static std::string prefill_role(const std::string& name) {
  if(!name.starts_with("blk."))return name;
  auto dot=name.find('.',4);require(dot!=std::string::npos,"layer buffer name");return "blk.*"+name.substr(dot);
}
bool prefill_persistent(const std::string& name) const {
  return name=="error"||name=="active"||name=="token_history"||name=="ple_metadata"||state_spares.count(name)||
         ends(name,".state")||ends(name,"history")||ends(name,".keys")||ends(name,".values")||ends(name,".raw")||ends(name,".pooled");
}
// Sites a prompt row runs: the fixture-0 single-row step without head, transport or host lookup kernels.
bool prefill_runs(const flash::Launch& l) const {
  if(v3_skip_half[size_t(&l-p.launches.data())])return false;
  if(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax")return false;
  return l.op!="handoff"&&l.op!="handoff_result";
}
void prefill_allocate() {
  if(!a.prefill_rows)return;
  require(a.cards==1&&resident,"batched prefill: one resident card per rank");
  const size_t M=size_t(a.prefill_rows);
  std::map<std::string,size_t> role_bytes;
  for(const auto& l:p.launches) {
    if(!prefill_runs(l))continue;
    prefill_sites.push_back(&l);
    std::vector<std::string> names(l.inputs.begin(),l.inputs.end());names.insert(names.end(),l.outputs.begin(),l.outputs.end());
    for(const auto& name:names) {
      if(name=="position"||name=="token"||prefill_persistent(name))continue;
      const auto& slot=buffers[0].at(name);const size_t bytes=slot.n*flash::scalar_bytes(slot.type);
      auto role=prefill_role(name);prefill_role_of[name]=role;role_bytes[role]=std::max(role_bytes[role],bytes);
    }
  }
  size_t total=0;
  for(const auto& [role,bytes]:role_bytes) {
    auto id=allocate(0,"prefill:"+role,bytes*M,Category::scratch,Lifetime::transaction);
    std::vector<uint8_t> zero(std::min(bytes*M,size_t(4194304)),0);
    for(size_t off=0;off<bytes*M;off+=zero.size())upload(0,id,off,zero.data(),std::min(zero.size(),bytes*M-off));
    prefill_shadows[role]={id,bytes};total+=bytes*M;
  }
  prefill_positions=allocate(0,"prefill:positions",M*4,Category::scratch,Lifetime::transaction);
  prefill_tokens=allocate(0,"prefill:tokens",M*4,Category::scratch,Lifetime::transaction);
  std::ostringstream o;o<<"{\"rows\":"<<M<<",\"roles\":"<<role_bytes.size()<<",\"buffers\":"<<prefill_role_of.size()
    <<",\"sites\":"<<prefill_sites.size()<<",\"shadow_bytes\":"<<total<<"}";
  save(a.output/"prefill-allocation.json",o.str());
}
Allocation prefill_shadow(const std::string& name) const {return prefill_shadows.at(prefill_role_of.at(name)).id;}
size_t prefill_row_bytes(const std::string& name) const {const auto& s=buffers[0].at(name);return s.n*flash::scalar_bytes(s.type);}
// Rank 0 host inputs: per-row lookup rows (embedding, PLE) with the token history advanced row by row.
void prefill_lookups(const int* tokens,int M) {
  for(int r=0;r<M;++r) {
    for(const auto& l:p.launches)if(l.op=="lookup") {
      lookup_ids[l.label]=lookup_input(l,tokens[r]);
      auto values=lookup_floats(l);const size_t bytes=values.size()*4;
      require(bytes==prefill_row_bytes(l.outputs[0]),"prefill lookup row extent");
      upload(0,prefill_shadow(l.outputs[0]),size_t(r)*bytes,values.data(),bytes);
    }
    history0=history1;history1=tokens[r];
  }
}
void prefill_linear(const flash::Launch& l,int M) {
  auto it=matrices.find(&l);
  if(it==matrices.end())it=matrices.emplace(&l,std::vector<Matrix>{matrix(l)}).first;
  Matrix m=it->second.at(0);
  require(prefill_row_bytes(l.inputs[0])*size_t(M)<=dev(0).arena.row(prefill_shadow(l.inputs[0])).bytes,"prefill linear input extent");
  m.x=prefill_shadow(l.inputs[0]);m.y=prefill_shadow(l.outputs[0]);
  if(l.op=="routed_gemv") {
    require(m.count==unsigned(p.g.top)&&m.routes&&m.status,"prefill routed site");
    m.routes=prefill_shadow(l.inputs[1]);m.status=prefill_shadow(l.outputs[1]);m.count=unsigned(p.g.top)*unsigned(M);
  } else {require(m.count==1&&!m.routes,"prefill dense site");m.tokens=unsigned(M);}
  gsq_linear_matrix(l,m);
}
void prefill_set_views(bool on) {
  auto& d=dev(0);d.row_views.clear();d.view_row=-1;
  if(!on)return;
  for(const auto& [name,role]:prefill_role_of)d.row_views[buffers[0].at(name).id]={prefill_shadows.at(role).id,prefill_row_bytes(name),false};
  d.row_views[buffers[0].at("position").id]={prefill_positions,4,false};
  if(buffers[0].count("token"))d.row_views[buffers[0].at("token").id]={prefill_tokens,4,false};
  for(const auto& [name,spare]:state_spares){auto active=buffers[0].at(name).id;d.row_views[active]={spare,0,true};d.row_views[spare]={active,0,true};}
}
// Run rows P0..P0+M-1. rows_in: rank 1's M input stream rows (nullptr on rank 0). rows_out: M output stream rows.
void prefill_chunk(int P0,const int* tokens,int M,const uint8_t* rows_in,uint8_t* rows_out) {
  require(a.prefill_rows>0&&M>=1&&M<=a.prefill_rows,"prefill chunk rows");
  require(P0>=0&&P0+M<=p.g.context,"prefill context bound");
  verify_configuration();guard();drain();
  require(integer(0,"position")==P0,"prefill position sequence");
  std::vector<int32_t> positions(M),ids(M);
  for(int r=0;r<M;++r){positions[r]=P0+r;ids[r]=tokens?tokens[r]:0;require(ids[r]>=0&&ids[r]<p.g.vocab,"prefill token bound");}
  upload(0,prefill_positions,0,positions.data(),size_t(M)*4);upload(0,prefill_tokens,0,ids.data(),size_t(M)*4);
  const size_t stream=stream_bytes();
  if(rows_in)upload(0,prefill_shadow("streams"),0,rows_in,size_t(M)*stream);
  else prefill_lookups(tokens,M);
  const int saved_extent=context_extent;
  std::map<std::pair<const flash::Launch*,int>,Prepared> extent_sites;
  uint64_t drained_at=submitted;
  try {
    prefill_set_views(true);
    for(const auto* l:prefill_sites) {
      if(l->op=="lookup")continue; // rows were written by the host above
      if(l->op=="gemv"||l->op=="routed_gemv"){dev(0).view_row=-1;prefill_linear(*l,M);continue;}
      const bool qsa=l->op=="qsa_select"||l->op=="qsa_attention";
      for(int r=0;r<M;++r) {
        dev(0).view_row=r;
        if(qsa) {
          const int bound=std::min(p.g.context,((P0+r+32)/32)*32);
          auto key=std::make_pair(l,bound);auto found=extent_sites.find(key);
          if(found==extent_sites.end()){context_extent=bound;found=extent_sites.emplace(key,prepare_site(*l)).first;context_extent=saved_extent;}
          const auto& bound_site=found->second;
          finish(0,bound_site.submit(dev(0),bound_site.spec,bound_site.bindings,controls[0],scores[0],probabilities[0],{}),false);
        } else execute_site(*l);
      }
      dev(0).view_row=-1;
      // Owner event ledger holds 16384 events; retire well before it fills.
      if(submitted-drained_at>6000){drain();drained_at=submitted;}
    }
    prefill_set_views(false);
  } catch(...) {context_extent=saved_extent;prefill_set_views(false);throw;}
  context_extent=saved_extent;
  drain();
  require(!integer(0,"error"),"sticky rank error in batched prefill");
  // The position after M single-row steps; banks end where M swaps leave them.
  const uint32_t next=uint32_t(P0+M);put(0,"position",&next,4);
  if(!state_spares.empty())for(int r=0;r<M%2;++r)swap_state_banks();
  if(rows_out){auto raw=readback(0,prefill_shadow("streams"),size_t(M)*stream);std::memcpy(rows_out,raw.data(),raw.size());}
  ++prefill_chunks;prefill_rows_done+=size_t(M);
}
