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
// Captured row replays: the commands an unchanged site issues for one row, captured once under that row's views and
// issued like the decode path's prepared sites. Keyed by site, row, QSA context extent (0 for other sites) and the
// recurrent bank pair (active and spare of one banked buffer; all banks swap together). Dropped when the device
// invalidates prepared commands.
using PrefillKey=std::tuple<const flash::Launch*,int,int,Allocation,Allocation>;
std::map<PrefillKey,std::vector<ownrt::PreparedCompute>> prefill_captured;
uint64_t prefill_generation=0,prefill_captures=0;
const std::vector<ownrt::PreparedCompute>& prefill_commands(const flash::Launch& l,int row,int extent) {
  if(dev(0).generation()!=prefill_generation){prefill_captured.clear();prefill_generation=dev(0).generation();}
  Allocation active=0,spare=0;if(!state_spares.empty()){active=buffers[0].at(state_spares.begin()->first).id;spare=state_spares.begin()->second;}
  const PrefillKey key{&l,row,extent,active,spare};
  if(auto found=prefill_captured.find(key);found!=prefill_captured.end())return found->second;
  auto& out=prefill_captured[key];const int saved_extent=context_extent;auto& d=dev(0);
  d.view_row=row;preparing_commands=true;d.begin_capture(out);
  try {
    if(extent){context_extent=extent;auto site=prepare_site(l);context_extent=saved_extent;site.submit(d,site.spec,site.bindings,controls[0],scores[0],probabilities[0],{});}
    else execute_site(l);
    d.end_capture();preparing_commands=false;d.view_row=-1;
  } catch(...) {d.end_capture();preparing_commands=false;d.view_row=-1;context_extent=saved_extent;prefill_captured.erase(key);throw;}
  ++prefill_captures;return out;
}
// Native multi-row sites: one launch for all M rows with Spec.tokens=M on the M-row buffers. These generic and
// specialised kernels loop rows inside the launch, each row with its single-row arithmetic (rows of a recurrence
// carry state through the output bank, so every row's state ends in the spare bank). OWNRT_PREFILL_NATIVE=0 replays
// them per row instead (diagnostic).
static int prefill_attention_rows() {static const int rows=[]{const char* e=std::getenv("OWNRT_PREFILL_ATTN_ROWS");int v=e?std::atoi(e):4; /* default 4: exact, 10.54 -> 10.25 ms/row on rank 1 at 3000 rows (2026-10-25) */return v<1?1:v>4?4:v;}();return rows;}
static bool prefill_native_op(const std::string& op) {
  static const std::set<std::string> ops{"gdn","conv","gdn_norm_gate","qsa_prepare","qsa_append_pool","qsa_select","hc_mix","silu_div4","silu_product","norm",
                                         "route","expert_gather","hc_combine","check_status"};
  static const bool enabled=[]{const char* e=std::getenv("OWNRT_PREFILL_NATIVE");return !e||e[0]!='0';}();
  return enabled&&ops.count(op);
}
bool prefill_native(const flash::Launch& l) const {
  if(!prefill_native_op(l.op))return false;
  const auto& s=prepared.at(&l).spec;
  if(l.op=="check_status")return s.special==Special::check_status; // any-nonzero over all rows' slot status
  if(l.op=="route"||l.op=="expert_gather"||l.op=="hc_combine") // SimpleNew kernels with per-row binding offsets
    return s.special==Special::normal&&(s.implementation==1||s.implementation==11)&&!s.fused_combine_norm;
  // round2's GDN (implementation 2) loops token rows like the generic kernel: row r reads the state row r-1 wrote.
  return s.special==Special::normal&&(s.implementation<=1||s.implementation==11||(l.op=="gdn"&&s.implementation==2))&&!s.fused_combine_norm;
}
void prefill_native_site(const flash::Launch& l,int P0,int M) {
  const int saved_extent=context_extent;
  if(l.op=="qsa_select")context_extent=std::min(p.g.context,((P0+M-1+32)/32)*32); // covers the chunk's last row
  auto site=prepare_site(l);context_extent=saved_extent;
  size_t k=0;
  for(const auto& name:l.inputs){if(prefill_role_of.count(name))site.bindings.at(k)=prefill_shadow(name);++k;}
  for(const auto& name:l.outputs){if(prefill_role_of.count(name))site.bindings.at(k)=prefill_shadow(name);++k;}
  if(l.op=="check_status") {
    // One status check over every row's slots: the sticky error is set exactly when some row's check would set it.
    require(!prefill_role_of.count("error"),"prefill status rows");
    for(size_t k=0;k<l.inputs.size()&&ends(l.inputs[k],".status");++k){require(prefill_role_of.count(l.inputs[k]),"prefill status rows");site.spec.sizes[k]*=size_t(M);}
  } else {
    site.spec.tokens=M;
    for(size_t j=0;j<l.inputs.size()+l.outputs.size();++j){
      const auto& name=j<l.inputs.size()?l.inputs[j]:l.outputs[j-l.inputs.size()];
      if(prefill_role_of.count(name))site.spec.row_bytes[j]=uint32_t(prefill_row_bytes(name));
    }
    site.spec.tmp_row_bytes=4096*4; // route's per-row temporary (2*32+2*512 floats) and gather's flags fit
  }
  finish(0,site.submit(dev(0),site.spec,site.bindings,controls[0],scores[0],probabilities[0],{}),false);
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
  uint64_t drained_at=submitted;
  bool banks_native=false,banks_replayed=false;
  // Diagnostic only (OWNRT_PREFILL_PROFILE=1): drain after every site and add its wall time to its op (linear sites
  // by weight format). Serializes the chunk, so it measures where time goes, never speed. No arithmetic change.
  static const bool profile=[]{const char* e=std::getenv("OWNRT_PREFILL_PROFILE");return e&&e[0]=='1';}();
  std::map<std::string,std::pair<int,double>> spent;
  try {
    prefill_set_views(true);
    for(const auto* l:prefill_sites) {
      if(l->op=="lookup")continue; // rows were written by the host above
      if(profile)drain();
      const auto site_start=std::chrono::steady_clock::now();
      bool banked_native=false;
      if(l->op=="gemv"||l->op=="routed_gemv")prefill_linear(*l,M);
      else if(prefill_native(*l)){prefill_native_site(*l,P0,M);banked_native=l->op=="gdn"||l->op=="conv";}
      else if(l->op=="qsa_attention"&&prefill_attention_rows()>1) {
        // Grouped rows (OWNRT_PREFILL_ATTN_ROWS=T, T<=4): one admit/tiles/combine launch set per T consecutive rows,
        // from row g's views, with the extent of the group's last row. Each row keeps its own query, ids, slot count and
        // causal bound, and combine stops at the row's own count, so its arithmetic equals its single-row replay.
        const int T=prefill_attention_rows();
        for(int g=0;g<M;g+=T) {
          const int rows=std::min(T,M-g),extent=std::min(p.g.context,((P0+g+rows-1+32)/32)*32);
          // Per-row bindings are the multi-row prefill shadows (as in prefill_native_site), each viewed at row g through
          // a temporary self-view; shared bindings (KV pools, controls) are unchanged.
          auto& d=dev(0);const int saved_extent=context_extent;context_extent=extent;
          auto site=prepare_site(*l);context_extent=saved_extent;site.spec.tokens=rows;
          std::vector<Allocation> viewed;size_t k=0;
          for(const auto* names:{&l->inputs,&l->outputs})for(const auto& name:*names){
            if(prefill_role_of.count(name)){const Allocation shadow=prefill_shadow(name);site.bindings.at(k)=shadow;
              require(!d.row_views.count(shadow),"prefill shadow already viewed");d.row_views[shadow]={shadow,prefill_row_bytes(name),false};viewed.push_back(shadow);}
            ++k;}
          d.view_row=g;
          try {finish(0,site.submit(d,site.spec,site.bindings,controls[0],scores[0],probabilities[0],{}),false);}
          catch(...){d.view_row=-1;for(auto v:viewed)d.row_views.erase(v);throw;}
          d.view_row=-1;for(auto v:viewed)d.row_views.erase(v);
        }
      }
      else {
        const bool qsa=l->op=="qsa_select"||l->op=="qsa_attention";
        for(int r=0;r<M;++r) {
          // Each row's QSA sites use the context extent its own single-row step admits.
          const int extent=qsa?std::min(p.g.context,((P0+r+32)/32)*32):0;
          for(const auto& cmd:prefill_commands(*l,r,extent)){auto event=dev(0).issue(cmd);finish(0,{event,event,1},false);}
        }
      }
      if(banked_native)banks_native=true;else if(l->op=="gdn"||l->op=="conv")banks_replayed=true;
      // OWNRT_PREFILL_PROFILE_SHAPE=1 (diagnostic) also keys linear sites by their rows x columns.
      static const bool profile_shape=[]{const char* e=std::getenv("OWNRT_PREFILL_PROFILE_SHAPE");return e&&e[0]=='1';}();
      if(profile){drain();std::string key=l->op=="gemv"||l->op=="routed_gemv"?l->op+":"+w.directory.at(l->weights.at(0)).grid:l->op;
        if(profile_shape&&(l->op=="gemv"||l->op=="routed_gemv")&&l->shape.size()==3)key+=":"+std::to_string(l->shape[1])+"x"+std::to_string(l->shape[2]);
        auto& entry=spent[key];++entry.first;entry.second+=ms(site_start);}
      // Owner event ledger holds 16384 events; retire well before it fills.
      if(submitted-drained_at>6000){drain();drained_at=submitted;}
    }
    prefill_set_views(false);
  } catch(...) {prefill_set_views(false);throw;}
  if(profile){std::ofstream o(a.output/"prefill-profile.jsonl",std::ios::app);o<<"{\"position\":"<<P0<<",\"rows\":"<<M<<
#ifndef OWN_RT_HOST_ONLY
    (reuse2::enabled()?",\"chunk\":"+std::to_string(reuse2::chunk_counter()):std::string())<<
#endif
    ",\"sites\":{";bool comma=false;
    for(const auto& [k,v]:spent){o<<(comma?",":"")<<ownrt::quote(k)<<":{\"count\":"<<v.first<<",\"ms\":"<<v.second<<"}";comma=true;}o<<"}}\n";}
  drain();
  require(!integer(0,"error"),"sticky rank error in batched prefill");
  // The position after M single-row steps; banks end where M swaps leave them.
  const uint32_t next=uint32_t(P0+M);put(0,"position",&next,4);
  // Replayed recurrences alternate banks per row (M single-row swaps); native ones leave every row in the spare bank.
  require(!(banks_native&&banks_replayed),"prefill recurrent sites must all be native or all replayed");
  if(!state_spares.empty())for(int r=0;r<(banks_native?1:M%2);++r)swap_state_banks();
  if(rows_out){auto raw=readback(0,prefill_shadow("streams"),size_t(M)*stream);std::memcpy(rows_out,raw.data(),raw.size());}
  ++prefill_chunks;prefill_rows_done+=size_t(M);
#ifndef OWN_RT_HOST_ONLY
  ++reuse2::chunk_counter(); // OWNRT_PREFILL_REUSE2_CYCLE diagnostic: the next chunk's tile configuration
#endif
}
