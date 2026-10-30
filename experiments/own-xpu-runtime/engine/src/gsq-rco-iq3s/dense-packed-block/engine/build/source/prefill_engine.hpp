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
//
// --tp-replicate (2026-10-29, research/tp/service-ready-2026-10-29): TP-native batched prefill. The sites are the TP
// plan's launches on both cards; each runs on its own card with that card's shadows, views, positions and tokens, so
// each card keeps its own layout (replicated buffers whole, head-split and compact-slot buffers compact) and nothing is
// copied between layouts. A compact buffer's shadow rows hold the card's compact extent (its writers emit compact rows
// back to back, as the M-row kernels read them). The TP sites with peer stores run multi-row:
// - tp_xgather / tp_xheads: one direct exchange per card over the chunk's M rows. The per-row layouts are uniform
//   strides (row halves: runs of R/2 every R; heads: runs of 1024 every 2048; compact expert slots: runs of 2560 every
//   5120), so one strided exchange covers all M rows. Each uses its own prefill flag slot (decode slot + 128), and both
//   cards are drained and that slot's counter and flag words zeroed before the pair is issued: the epoch is then 1 on
//   both cards whatever the row count, the decode slots' epochs are untouched, and no peer store can reach a shadow
//   that the peer's earlier sites still use.
// - tp_route_compact: RouteCompact over the M x top routes (this card's slots of every row, in order), and the same
//   selection of the expert input rows (SlotRowsCompact) for the compact gate/up launches, which read one input row per
//   slot. Each slot keeps its route, input row, kernel and arithmetic.
// Without --tp-replicate every path below is the one-card path (card 0) unchanged.
struct PrefillShadow {Allocation id=0;size_t row_bytes=0;};
std::array<std::map<std::string,PrefillShadow>,2> prefill_shadows;   // per card, by role: "blk.*.<suffix>" for layer buffers
std::map<std::string,std::string> prefill_role_of;     // plan buffer name -> role
std::vector<const flash::Launch*> prefill_sites;
std::array<Allocation,2> prefill_positions{},prefill_tokens{};
std::array<Allocation,2> xg_order{},xg_tiles{},xg_count{};size_t xg_capacity=0;
std::array<Allocation,2> prefill_slot_x{};             // TP: this card's expert input rows (compact slots) of the chunk
uint64_t prefill_chunks=0,prefill_rows_done=0;
int prefill_cards() const {return a.tp_replicate?2:1;}
static constexpr uint32_t prefill_exchange_slot_base=128;
// Request-local ring accounting: native recurrence chunks publish once into the
// spare bank, while scalar/replayed rows swap per row. No model state is changed.
unsigned prefill_bank_parity_bias=0;
void prefill_finish_banks(int rows,bool native,bool replayed) {
  require(rows>0&&rows<=a.prefill_rows,"prefill bank completion rows");
  require(!(native&&replayed),"prefill recurrent sites must all be native or all replayed");
  if(state_spares.empty())return;
  const unsigned swaps=native?1u:unsigned(rows%2);
  for(unsigned r=0;r<swaps;++r)swap_state_banks();
  // Bulk admission excludes pending speculative rows. This bias is fixed
  // throughout scalar speculation/rollback and cleared only by owner reset.
  if(a.pipeline_ring)prefill_bank_parity_bias^=swaps^unsigned(rows%2);
}
unsigned ring_expected_bank_parity(int position) const {
  require(position>=0&&prefill_bank_parity_bias<=1,"ring bank accounting bounds");
  return a.pipeline_first()?(unsigned(position%2)^prefill_bank_parity_bias):0u;
}
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
// Bytes of one shadow row of `name` on card c: the buffer's bytes, or under TP a head-split / compact-slot buffer's
// compact extent on that card (Engine::head_split_layout), which its M-row writers and readers use as the row stride.
size_t prefill_row_bytes(int c,const std::string& name) const {
  const auto& s=buffers[size_t(c)].at(name);
  if(a.tp_replicate)if(auto h=head_split_layout.find(name);h!=head_split_layout.end()){size_t n=0;for(const auto& r:h->second[size_t(c)])n+=r[2];require(n>0&&n<=s.n,"TP compact row extent: "+name);return n*flash::scalar_bytes(s.type);}
  return s.n*flash::scalar_bytes(s.type);
}
void prefill_allocate() {
  if(!a.prefill_rows)return;
  require((a.cards==1||(a.tp_replicate&&a.cards==2))&&resident,"batched prefill: one resident card per rank (or --tp-replicate)");
  const size_t M=size_t(a.prefill_rows);const int C=prefill_cards();
  std::array<std::map<std::string,size_t>,2> card_role_bytes;
  for(const auto& l:p.launches) {
    if(!prefill_runs(l))continue;
    require(l.card>=0&&l.card<C,"prefill site card");
    prefill_sites.push_back(&l);
    std::vector<std::string> names(l.inputs.begin(),l.inputs.end());names.insert(names.end(),l.outputs.begin(),l.outputs.end());
    for(const auto& name:names) {
      if(name=="position"||name=="token"||prefill_persistent(name))continue;
      const size_t bytes=prefill_row_bytes(l.card,name);
      auto role=prefill_role(name);prefill_role_of[name]=role;auto& rb=card_role_bytes[size_t(l.card)][role];rb=std::max(rb,bytes);
    }
  }
  std::ostringstream cards_json;
  for(int c=0;c<C;++c){
  const auto& role_bytes=card_role_bytes[size_t(c)];
  size_t total=0,unpacked=0;
  // OWNRT_PREFILL_SHADOW_PACK=1 (lab 2026-10-26, default off; rank 1 only): roles whose live ranges never overlap share
  // one allocation. A chunk runs prefill_sites in this order (every row of a site before the next site), and only
  // prefill_chunk reaches the shadows. A role's value lives from the site that writes it to its last reader before the
  // next write; a role read before any write (the input rows), and every non-layer role, lives for the whole chunk.
  // Two roles share an allocation only if none of their live ranges intersect. So every read sees the bytes its role's
  // last write left, exactly as with private shadows; two roles of one site never share. Largest role first, best fit.
  static const bool pack_env=[]{const char* e=std::getenv("OWNRT_PREFILL_SHADOW_PACK");return e&&e[0]=='1';}();
  std::map<std::string,size_t> slot_of;std::vector<size_t> slot_bytes;
  if(pack_env&&a.rank==1&&a.gsq_packed&&!a.mini) {
    using Segment=std::pair<size_t,size_t>;std::map<std::string,std::vector<Segment>> live;std::map<std::string,std::pair<size_t,size_t>> open;
    const size_t n=prefill_sites.size();
    for(size_t i=0;i<n;++i){const auto& l=*prefill_sites[i];if(l.card!=c)continue; // this card's sites (TP: a peer store lands after a drain)
      for(const auto& name:l.inputs)if(prefill_role_of.count(name)){const auto& r=prefill_role_of.at(name);auto it=open.find(r);
        if(it==open.end())open[r]={0,i};else it->second.second=i;}
      for(const auto& name:l.outputs)if(prefill_role_of.count(name)){const auto& r=prefill_role_of.at(name);auto it=open.find(r);
        if(it!=open.end())live[r].push_back(it->second);open[r]={l.op=="lookup"?0:i,i};}
    }
    for(const auto& [r,seg]:open)live[r].push_back(seg);
    for(auto& [r,segs]:live)if(!r.starts_with("blk.*")){segs.assign(1,{0,n});}
    for(const auto& [r,bytes]:role_bytes)require(live.count(r),"prefill shadow role without a site");
    auto overlap=[&](const std::string& x,const std::string& y){for(const auto& a0:live.at(x))for(const auto& b0:live.at(y))if(a0.first<=b0.second&&b0.first<=a0.second)return true;return false;};
    std::vector<std::pair<size_t,std::string>> order;for(const auto& [r,bytes]:role_bytes)order.push_back({bytes,r});
    std::sort(order.begin(),order.end(),[](const auto& x,const auto& y){return x.first!=y.first?x.first>y.first:x.second<y.second;});
    std::vector<std::vector<std::string>> members;
    for(const auto& [bytes,r]:order){size_t best=SIZE_MAX;
      for(size_t k=0;k<members.size();++k){bool ok=true;for(const auto& q:members[k])if(overlap(r,q)){ok=false;break;}
        if(ok&&(best==SIZE_MAX||slot_bytes[k]<slot_bytes[best]))best=k;}
      if(best==SIZE_MAX){best=members.size();members.emplace_back();slot_bytes.push_back(0);}
      members[best].push_back(r);slot_bytes[best]=std::max(slot_bytes[best],bytes);slot_of[r]=best;}
  }
  if(!slot_of.empty()) {
    std::vector<Allocation> ids;
    for(size_t k=0;k<slot_bytes.size();++k){const size_t bytes=slot_bytes[k]*M;
      auto id=allocate(c,"prefill:pack"+std::to_string(k),bytes,Category::scratch,Lifetime::transaction);
      std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)),0);
      for(size_t off=0;off<bytes;off+=zero.size())upload(c,id,off,zero.data(),std::min(zero.size(),bytes-off));
      ids.push_back(id);total+=bytes;}
    for(const auto& [role,bytes]:role_bytes){prefill_shadows[size_t(c)][role]={ids.at(slot_of.at(role)),bytes};unpacked+=bytes*M;}
    std::ostringstream o;o<<"{\"slots\":[";for(size_t k=0;k<slot_bytes.size();++k){o<<(k?",":"")<<"{\"bytes\":"<<slot_bytes[k]*M<<",\"roles\":[";bool comma=false;
      for(const auto& [r,slot]:slot_of)if(slot==k){o<<(comma?",":"")<<ownrt::quote(r);comma=true;}o<<"]}";}
    o<<"]}";save(a.output/(c?"prefill-shadow-pack-card1.json":"prefill-shadow-pack.json"),o.str());
  } else
  for(const auto& [role,bytes]:role_bytes) {
    auto id=allocate(c,"prefill:"+role,bytes*M,Category::scratch,Lifetime::transaction);
    std::vector<uint8_t> zero(std::min(bytes*M,size_t(4194304)),0);
    for(size_t off=0;off<bytes*M;off+=zero.size())upload(c,id,off,zero.data(),std::min(zero.size(),bytes*M-off));
    prefill_shadows[size_t(c)][role]={id,bytes};total+=bytes*M;unpacked+=bytes*M;
  }
#ifndef OWN_RT_HOST_ONLY
  if(xgroup::enabled()) { // expert-grouped routed sites: slot order, tile descriptors and tile count for top*M slots
    xg_capacity=size_t(p.g.top)*M;
    xg_order[size_t(c)]=allocate(c,"prefill:xg-order",xg_capacity*4,Category::scratch,Lifetime::transaction);
    xg_tiles[size_t(c)]=allocate(c,"prefill:xg-tiles",xg_capacity*xgroup::desc_words*4,Category::scratch,Lifetime::transaction);
    xg_count[size_t(c)]=allocate(c,"prefill:xg-count",64,Category::scratch,Lifetime::transaction);
  }
#endif
  prefill_positions[size_t(c)]=allocate(c,"prefill:positions",M*4,Category::scratch,Lifetime::transaction);
  prefill_tokens[size_t(c)]=allocate(c,"prefill:tokens",M*4,Category::scratch,Lifetime::transaction);
  if(prefill_moe_native()){bool moe=false;for(const auto* l:prefill_sites)moe=moe||(l->card==c&&l->op=="moe_combine");
    if(moe){require(a.f32_activations,"OWNRT_PREFILL_MOE_NATIVE: F32 exact mode");
      prefill_moe_mix[size_t(c)]=allocate(c,"prefill:moe-mixture",M*size_t(p.g.h)*4,Category::scratch,Lifetime::transaction);
      prefill_moe_ones[size_t(c)]=allocate(c,"prefill:moe-ones",M*4,Category::scratch,Lifetime::transaction);
      const std::vector<float> ones(M,1.f);upload(c,prefill_moe_ones[size_t(c)],0,ones.data(),M*4);total+=M*size_t(p.g.h)*4+M*4;}}
  size_t slot_x=0;
  if(a.tp_replicate){ // compact gate/up input rows: this card's slots of the M rows (largest expert input row)
    for(const auto* l:prefill_sites)if(l->card==c&&l->op=="routed_gemv"&&l->slots&&!ends(l->inputs.at(0),".expsact"))slot_x=std::max(slot_x,size_t(l->slots)*prefill_row_bytes(c,l->inputs.at(0))/size_t(p.g.top));
    if(slot_x){prefill_slot_x[size_t(c)]=allocate(c,"prefill:slot-x",slot_x*M,Category::scratch,Lifetime::transaction);total+=slot_x*M;}
  }
  cards_json<<(c?",":"")<<"{\"card\":"<<c<<",\"roles\":"<<role_bytes.size()<<",\"shadow_bytes\":"<<total<<",\"slot_x_bytes\":"<<slot_x*M
    <<(slot_of.empty()?std::string():",\"packed_slots\":"+std::to_string(slot_bytes.size())+",\"unpacked_bytes\":"+std::to_string(unpacked))<<"}";
  if(c==0){std::ostringstream o;o<<"{\"rows\":"<<M<<",\"roles\":"<<role_bytes.size()<<",\"buffers\":"<<prefill_role_of.size()
    <<",\"sites\":"<<prefill_sites.size()<<",\"shadow_bytes\":"<<total<<(slot_of.empty()?std::string():",\"packed_slots\":"+std::to_string(slot_bytes.size())+",\"unpacked_bytes\":"+std::to_string(unpacked));
    if(C==1){o<<"}";save(a.output/"prefill-allocation.json",o.str());}}
  }
  if(C==2){std::ostringstream o;o<<"{\"rows\":"<<M<<",\"buffers\":"<<prefill_role_of.size()<<",\"sites\":"<<prefill_sites.size()<<",\"tp\":true,\"cards\":["<<cards_json.str()<<"]}";
    save(a.output/"prefill-allocation.json",o.str());}
}
// Captured row replays: the commands an unchanged site issues for one row, captured once under that row's views and
// issued like the decode path's prepared sites. Keyed by site, row, QSA context extent (0 for other sites) and the
// recurrent bank pair (active and spare of one banked buffer; all banks swap together). Dropped when the device
// invalidates prepared commands.
using PrefillKey=std::tuple<const flash::Launch*,int,int,Allocation,Allocation>;
std::array<std::map<PrefillKey,std::vector<ownrt::PreparedCompute>>,2> prefill_captured; // per card
std::array<uint64_t,2> prefill_generation{};uint64_t prefill_captures=0;
const std::vector<ownrt::PreparedCompute>& prefill_commands(const flash::Launch& l,int row,int extent) {
  const int c=l.card;auto& captured=prefill_captured.at(size_t(c));
  if(dev(c).generation()!=prefill_generation[size_t(c)]){captured.clear();prefill_generation[size_t(c)]=dev(c).generation();}
  Allocation active=0,spare=0;if(!spares(c).empty()){active=buffers[size_t(c)].at(spares(c).begin()->first).id;spare=spares(c).begin()->second;}
  const PrefillKey key{&l,row,extent,active,spare};
  if(auto found=captured.find(key);found!=captured.end())return found->second;
  auto& out=captured[key];const int saved_extent=context_extent;auto& d=dev(c);
  d.view_row=row;preparing_commands=true;d.begin_capture(out);
  try {
    if(extent){context_extent=extent;auto site=prepare_site(l);context_extent=saved_extent;site.submit(d,site.spec,site.bindings,controls[size_t(c)],scores[size_t(c)],probabilities[size_t(c)],{});}
    else execute_site(l);
    d.end_capture();preparing_commands=false;d.view_row=-1;
  } catch(...) {d.end_capture();preparing_commands=false;d.view_row=-1;context_extent=saved_extent;captured.erase(key);throw;}
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
  const int c=l.card;const int saved_extent=context_extent;
  if(l.op=="qsa_select")context_extent=std::min(p.g.context,((P0+M-1+32)/32)*32); // covers the chunk's last row
  auto site=prepare_site(l);context_extent=saved_extent;
  size_t k=0;
  for(const auto& name:l.inputs){if(prefill_role_of.count(name))site.bindings.at(k)=prefill_shadow(c,name);++k;}
  for(const auto& name:l.outputs){if(prefill_role_of.count(name))site.bindings.at(k)=prefill_shadow(c,name);++k;}
  if(l.op=="check_status") {
    // One status check over every row's slots: the sticky error is set exactly when some row's check would set it.
    require(!prefill_role_of.count("error"),"prefill status rows");
    for(size_t k=0;k<l.inputs.size()&&ends(l.inputs[k],".status");++k){require(prefill_role_of.count(l.inputs[k]),"prefill status rows");site.spec.sizes[k]*=size_t(M);}
  } else {
    site.spec.tokens=M;
    for(size_t j=0;j<l.inputs.size()+l.outputs.size();++j){
      const auto& name=j<l.inputs.size()?l.inputs[j]:l.outputs[j-l.inputs.size()];
      if(prefill_role_of.count(name))site.spec.row_bytes[j]=uint32_t(prefill_row_bytes(c,name));
    }
    site.spec.tmp_row_bytes=4096*4; // route's per-row temporary (2*32+2*512 floats) and gather's flags fit
  }
  finish(c,site.submit(dev(c),site.spec,site.bindings,controls[size_t(c)],scores[size_t(c)],probabilities[size_t(c)],{}),false);
}
// QSA select rows per native launch: its specialised scratch holds tokens x ceil(context/4) floats in the 8 MiB
// operator scratch (128 rows at context 65536). Longer chunks run the native select in groups of at most that many rows,
// each from row g's views exactly as the grouped attention below (position/token views give row g its own position;
// shadows are viewed at row g), with the extent its last row admits. Each row's arithmetic is its single-row select.
int prefill_select_rows() const {return std::max(1,int(size_t(8)*1024*1024/(size_t(4)*((size_t(p.g.context)+3)/4))));}
void prefill_native_group(const flash::Launch& l,int P0,int g,int rows) {
  const int c=l.card;auto& d=dev(c);const int saved_extent=context_extent;
  context_extent=std::min(p.g.context,((P0+g+rows-1+32)/32)*32);
  auto site=prepare_site(l);context_extent=saved_extent;
  std::vector<Allocation> viewed;size_t k=0;
  for(const auto* names:{&l.inputs,&l.outputs})for(const auto& name:*names){
    if(prefill_role_of.count(name)){const Allocation shadow=prefill_shadow(c,name);site.bindings.at(k)=shadow;site.spec.row_bytes[k]=uint32_t(prefill_row_bytes(c,name));
      if(!d.row_views.count(shadow)){d.row_views[shadow]={shadow,prefill_row_bytes(c,name),false};viewed.push_back(shadow);}}
    ++k;}
  site.spec.tokens=rows;site.spec.tmp_row_bytes=4096*4;
  d.view_row=g;
  try {finish(c,site.submit(d,site.spec,site.bindings,controls[size_t(c)],scores[size_t(c)],probabilities[size_t(c)],{}),false);}
  catch(...){d.view_row=-1;for(auto v:viewed)d.row_views.erase(v);throw;}
  d.view_row=-1;for(auto v:viewed)d.row_views.erase(v);
}
Allocation prefill_shadow(int c,const std::string& name) const {return prefill_shadows[size_t(c)].at(prefill_role_of.at(name)).id;}
// OWNRT_PREFILL_SPECIAL_ROWS=1 (2026-10-30, research/tp/prefill-host-2026-10-30; default off): the glue ops a prompt row
// replays one row at a time (begin, commit, broadcast, ple_hash, ple_gate, ple_add; 256 launches per site and card) run
// as one launch over the chunk's M rows: each row-major binding is its prefill shadow, `token` and `position` are the
// chunk's per-row arrays (begin and commit also read and write their own row of the trailing position binding), and the
// persistent ones (error, active, token_history, ple_metadata) stay shared. The adapter runs row r with the unchanged
// single-row body; ple_hash's rows run in order (its token history carries from row to row).
static bool prefill_special_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_SPECIAL_ROWS");return e&&e[0]=='1';}();return on;}
static bool prefill_special_row_op(const std::string& op){return op=="begin"||op=="commit"||op=="broadcast"||op=="ple_hash"||op=="ple_gate"||op=="ple_add";}
void prefill_special_rows_site(const flash::Launch& l,int M) {
  const int c=l.card;auto site=prepare_site(l);size_t k=0;
  for(const auto* names:{&l.inputs,&l.outputs})for(const auto& name:*names){
    require(k<20,"prefill special rows: binding count");
    if(prefill_role_of.count(name)){site.bindings.at(k)=prefill_shadow(c,name);site.spec.row_bytes[k]=uint32_t(prefill_row_bytes(c,name));}
    else if(name=="position"){site.bindings.at(k)=prefill_positions[size_t(c)];site.spec.row_bytes[k]=4;}
    else if(name=="token"){site.bindings.at(k)=prefill_tokens[size_t(c)];site.spec.row_bytes[k]=4;}
    else {require(prefill_persistent(name),"prefill special rows: unexpected binding "+name);site.spec.row_bytes[k]=0;}
    ++k;}
  require(int(k)==site.spec.ni+site.spec.no,"prefill special rows: binding layout");
  if(l.op=="begin"||l.op=="commit")site.bindings.at(size_t(site.spec.ni+site.spec.no+site.spec.nw)+2)=prefill_positions[size_t(c)];
  site.spec.tokens=M;
  finish(c,site.submit(dev(c),site.spec,site.bindings,controls[size_t(c)],scores[size_t(c)],probabilities[size_t(c)],{}),false);
}
// OWNRT_PREFILL_MOE_NATIVE=1 (2026-10-29, research/tp/prefill-speed-2026-10-29; default off; F32 exact mode): moe_combine
// for all M rows in two launches per card instead of M replays of its two single-row commands. execute_site's moe_combine
// is (1) the F32 epilogue (mixture = sum over slots 0..9 of expsdown[slot] * prob[slot], into the engine's one-row
// mixture_out) and (2) the moe_combine site on (mixture_out, one, shexpdown, shared_gate). Here (1) is the same
// per-element expression over the M rows' expsdown/prob shadows into an M-row mixture buffer (epilogue_f32_rows) and (2)
// the same site with tokens=M on the M-row mixture, an M-row buffer of ones, and the shexpdown, shared_gate and moe
// shadows (the generic/ew kernel computes row r's elements at idx = r*width + k with the single-row expression).
static bool prefill_moe_native(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_MOE_NATIVE");return e&&e[0]=='1';}();return on;}
std::array<Allocation,2> prefill_moe_mix{},prefill_moe_ones{};
void prefill_moe_combine(const flash::Launch& l,int M) {
  const int c=l.card;
  require(a.f32_activations&&l.inputs.size()>=4&&l.outputs.size()==1&&prefill_moe_mix[size_t(c)]&&prefill_moe_ones[size_t(c)],"prefill moe_combine rows admission");
  for(int j=0;j<4;++j)require(prefill_role_of.count(l.inputs[size_t(j)]),"prefill moe_combine input rows: "+l.inputs[size_t(j)]);
  require(prefill_role_of.count(l.outputs[0]),"prefill moe_combine output rows");
  const size_t H=size_t(p.g.h),down=prefill_row_bytes(c,l.inputs[0]),prob=prefill_row_bytes(c,l.inputs[1]);
  require(down==size_t(10)*H*4&&prob==40&&prefill_row_bytes(c,l.inputs[2])==H*4&&prefill_row_bytes(c,l.inputs[3])==4&&prefill_row_bytes(c,l.outputs[0])==H*4,"prefill moe_combine row geometry");
  finish(c,iq3::kopt4::epilogue_f32_rows(dev(c),prefill_shadow(c,l.inputs[0]),prefill_shadow(c,l.inputs[1]),prefill_moe_mix[size_t(c)],unsigned(H),unsigned(M),unsigned(down/4),unsigned(prob/4)),false);
  auto site=prepare_site(l);
  require(site.bindings.size()>l.inputs.size()&&site.bindings.at(0)==mixture_out[size_t(c)]&&site.bindings.at(1)==one[size_t(c)],"prefill moe_combine site bindings");
  site.bindings.at(0)=prefill_moe_mix[size_t(c)];site.bindings.at(1)=prefill_moe_ones[size_t(c)];
  site.bindings.at(2)=prefill_shadow(c,l.inputs[2]);site.bindings.at(3)=prefill_shadow(c,l.inputs[3]);
  site.bindings.at(l.inputs.size())=prefill_shadow(c,l.outputs[0]);
  site.spec.tokens=M;
  finish(c,site.submit(dev(c),site.spec,site.bindings,controls[size_t(c)],scores[size_t(c)],probabilities[size_t(c)],{}),false);
}
// Rank 0 host inputs: per-row lookup rows (embedding, PLE) with the token history advanced row by row. Under TP each
// lookup's card-0 rows are computed once and uploaded to both cards (its card-1 twin reads the same row).
// OWNRT_PREFILL_LOOKUP_BATCH=1 (2026-10-29, research/tp/prefill-speed-2026-10-29; default off): the same rows, computed
// in the same order with the same history, are gathered on the host and written with one upload per lookup and card
// (row r at byte r*bytes of the M-row shadow, where the per-row upload put it) instead of one synchronous upload per
// row, lookup and card (1,024 per 256-row chunk under TP). Every device byte is unchanged.
static bool prefill_lookup_batch(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_LOOKUP_BATCH");return e&&e[0]=='1';}();return on;}
// OWNRT_PREFILL_LOOKUP_THREADS=N (2026-10-30, research/tp/prefill-host-2026-10-30; with OWNRT_PREFILL_LOOKUP_BATCH=1; default
// off): the chunk's lookup rows are dequantized by N host threads. The ids are computed first, row by row in order with
// the advancing token history, exactly as the sequential loop (lookup_input); then each thread converts a contiguous
// range of rows (the same gsq::element per element as lookup_floats, from the resident table bytes read() returns) into
// its own slice of the chunk's row buffer. The bytes uploaded, lookup_ids, history and read()'s counters end equal.
// Falls back to the sequential loop when a table is not resident.
static int prefill_lookup_threads(){static const int n=[]{const char* e=std::getenv("OWNRT_PREFILL_LOOKUP_THREADS");int v=e?std::atoi(e):0;return v<0?0:v>16?16:v;}();return n;}
bool prefill_lookup_rows_threaded(const std::vector<const flash::Launch*>& sites,const int* tokens,int M,std::vector<std::vector<float>>& rows,std::vector<size_t>& row_bytes){
  struct Table {std::string name;unsigned type=0;size_t row_bytes=0,columns=0,rows=0,ids=0;bool i64=false;};
  std::vector<Table> tables;
  for(const auto* l:sites){
    const auto input=buffers[size_t(l->card)].at(l->inputs[0]);const auto& t=w.directory.at(l->weights[0]);const auto type=flash::grid_type(t.grid);const auto fmt=iq3::layout(type);
    Table x{t.name,unsigned(type),size_t(t.shape.back())/fmt.elements*fmt.bytes,size_t(t.shape.back()),size_t(t.shape[0]),input.n,input.type==Scalar::i64};
    if(!w.resident(x.name,0,x.row_bytes))return false; // not resident: the sequential loop
    tables.push_back(x);
  }
  // 1. ids in row order (the history advances row by row), as the sequential loop computes them
  std::vector<std::vector<std::vector<uint8_t>>> ids(sites.size(),std::vector<std::vector<uint8_t>>(size_t(M)));
  for(int r=0;r<M;++r){for(size_t j=0;j<sites.size();++j)ids[j][size_t(r)]=lookup_input(*sites[j],tokens[r]);history0=history1;history1=tokens[r];}
  for(size_t j=0;j<sites.size();++j)lookup_ids[sites[j]->label]=ids[j][size_t(M-1)];
  for(size_t j=0;j<sites.size();++j){row_bytes[j]=tables[j].ids*tables[j].columns*4;
    for(int c=0;c<prefill_cards();++c)require(row_bytes[j]==prefill_row_bytes(c,sites[j]->outputs[0]),"prefill lookup row extent");
    rows[j].assign(size_t(M)*tables[j].ids*tables[j].columns,0.f);}
  // 2. values: rows split into contiguous ranges, one per thread
  const int T=std::min(prefill_lookup_threads(),M);std::vector<std::thread> pool;std::vector<std::string> errors(static_cast<size_t>(T),std::string());std::vector<size_t> bytes_read(static_cast<size_t>(T),0);
  auto work=[&](int t){try{const int r0=M*t/T,r1=M*(t+1)/T;
    for(size_t j=0;j<tables.size();++j){const auto& x=tables[j];
      for(int r=r0;r<r1;++r){const auto& raw=ids[j][size_t(r)];float* out=rows[j].data()+size_t(r)*x.ids*x.columns;
        for(size_t k=0;k<x.ids;++k){int64_t id;if(x.i64)std::memcpy(&id,raw.data()+k*8,8);else{int32_t v;std::memcpy(&v,raw.data()+k*4,4);id=v;}
          if(id<0||size_t(id)>=x.rows)throw std::runtime_error("lookup bounds");
          const uint8_t* row=w.resident(x.name,size_t(id)*x.row_bytes,x.row_bytes);if(!row)throw std::runtime_error("lookup table not resident");
          bytes_read[size_t(t)]+=x.row_bytes;const std::span<const uint8_t> span(row,x.row_bytes);
          for(size_t e=0;e<x.columns;++e)out[k*x.columns+e]=gsq::element(x.type,span,x.columns,e);}}}}
    catch(const std::exception& ex){errors[size_t(t)]=ex.what();}};
  for(int t=1;t<T;++t)pool.emplace_back(work,t);
  work(0);for(auto& th:pool)th.join();
  for(const auto& e:errors)require(e.empty(),"prefill lookup thread: "+e);
  for(size_t j=0;j<tables.size();++j)for(int r=0;r<M;++r)for(size_t k=0;k<tables[j].ids;++k)w.count_read(tables[j].row_bytes); // read()'s counters, as the sequential loop leaves them
  return true;
}
void prefill_lookups(const int* tokens,int M) {
  if(prefill_lookup_batch()) {
    std::vector<const flash::Launch*> sites;for(const auto& l:p.launches)if(l.op=="lookup"&&l.card==0)sites.push_back(&l);
    std::vector<std::vector<float>> rows(sites.size());std::vector<size_t> row_bytes(sites.size(),0);
    if(prefill_lookup_threads()>1&&prefill_lookup_rows_threaded(sites,tokens,M,rows,row_bytes)){
      for(size_t j=0;j<sites.size();++j)for(int c=0;c<prefill_cards();++c){
        require(rows[j].size()*4==size_t(M)*row_bytes[j],"prefill lookup chunk extent");
        upload(c,prefill_shadow(c,sites[j]->outputs[0]),0,rows[j].data(),rows[j].size()*4);}
      return;
    }
    for(int r=0;r<M;++r) {
      for(size_t j=0;j<sites.size();++j) {
        const auto& l=*sites[j];
        lookup_ids[l.label]=lookup_input(l,tokens[r]);
        auto values=lookup_floats(l);const size_t bytes=values.size()*4;
        if(!r){for(int c=0;c<prefill_cards();++c)require(bytes==prefill_row_bytes(c,l.outputs[0]),"prefill lookup row extent");row_bytes[j]=bytes;rows[j].reserve(size_t(M)*values.size());}
        require(bytes==row_bytes[j],"prefill lookup row extent");
        rows[j].insert(rows[j].end(),values.begin(),values.end());
      }
      history0=history1;history1=tokens[r];
    }
    for(size_t j=0;j<sites.size();++j)for(int c=0;c<prefill_cards();++c){
      require(rows[j].size()*4==size_t(M)*row_bytes[j],"prefill lookup chunk extent");
      upload(c,prefill_shadow(c,sites[j]->outputs[0]),0,rows[j].data(),rows[j].size()*4);}
    return;
  }
  for(int r=0;r<M;++r) {
    for(const auto& l:p.launches)if(l.op=="lookup"&&l.card==0) {
      lookup_ids[l.label]=lookup_input(l,tokens[r]);
      auto values=lookup_floats(l);const size_t bytes=values.size()*4;
      for(int c=0;c<prefill_cards();++c){
        require(bytes==prefill_row_bytes(c,l.outputs[0]),"prefill lookup row extent");
        upload(c,prefill_shadow(c,l.outputs[0]),size_t(r)*bytes,values.data(),bytes);}
    }
    history0=history1;history1=tokens[r];
  }
}
void prefill_linear(const flash::Launch& l,int M) {
  const int c=l.card;
  auto it=matrices.find(&l);
  if(it==matrices.end())it=matrices.emplace(&l,std::vector<Matrix>{matrix(l)}).first;
  Matrix m=it->second.at(0);
  require(prefill_row_bytes(c,l.inputs[0])*size_t(M)<=dev(c).arena.row(prefill_shadow(c,l.inputs[0])).bytes,"prefill linear input extent");
  m.x=prefill_shadow(c,l.inputs[0]);m.y=prefill_shadow(c,l.outputs[0]);
  if(l.op=="routed_gemv") {
    const unsigned slots=l.slots?unsigned(l.slots):unsigned(p.g.top); // TP compact slots: this card's slots of each row
    require(m.count==slots&&m.routes&&m.status,"prefill routed site");
    m.routes=prefill_shadow(c,l.inputs[1]);m.status=prefill_shadow(c,l.outputs[1]);m.count=slots*unsigned(M);
    // Compact gate/up read one input row per slot: this card's slots' rows, selected at tp_route_compact.
    if(l.slots&&!ends(l.inputs[0],".expsact")){require(prefill_slot_x[size_t(c)]!=0,"TP prefill compact expert input rows");m.x=prefill_slot_x[size_t(c)];}
  } else {require(m.count==1&&!m.routes,"prefill dense site");m.tokens=unsigned(M);}
  if(!(l.op=="routed_gemv"&&prefill_experts_site(l,m)))gsq_linear_matrix(l,m);
  // Diagnostic only (OWNRT_PREFILL_ROUTE_DUMP=<file>): after each routed site, drain and append its M*top routes
  // (record: u32 label length, label, u32 rows M, u32 slots, then slots x {expert_id,row_begin,row_count}).
  static const char* route_dump=std::getenv("OWNRT_PREFILL_ROUTE_DUMP");
  if(route_dump&&l.op=="routed_gemv") {
    drain();auto raw=readback(0,m.routes,size_t(m.count)*sizeof(iq3::Route));
    std::ofstream o(route_dump,std::ios::app|std::ios::binary);const uint32_t head[3]{uint32_t(l.label.size()),uint32_t(M),m.count};
    o.write(reinterpret_cast<const char*>(head),4);o.write(l.label.data(),l.label.size());o.write(reinterpret_cast<const char*>(head+1),8);
    o.write(reinterpret_cast<const char*>(raw.data()),raw.size());
  }
}
// Expert-grouped routed site (OWNRT_PREFILL_EXPERTS=1, prefill_experts.hpp): the same decode values as the kernel that
// gsq_linear_matrix would select for this site (IQ3_XXS block sites, gsqn packed rows, kopt routed rows), grouped by
// expert so each expert row is decoded once per tile of slots. Returns false (existing path) for anything else.
bool prefill_experts_site(const flash::Launch& l,const Matrix& m) {
#ifdef OWN_RT_HOST_ONLY
  (void)l;(void)m;return false;
#else
  if(!xgroup::enabled()||!xg_order[size_t(l.card)])return false;
  if(xgroup2::applies(m.count))return false; // OWNRT_EXPERTS_GROUPED: small chunks take the grouped one-row kernels
  if(m.activation!=iq3::Type::F32||m.output_type!=iq3::Type::F32||m.fp32||m.tokens!=1||!m.routes||!m.status||!m.count||!m.experts)return false;
  const size_t c=size_t(l.card);
  if((m.span&&m.span!=m.rows)||m.count>xg_capacity||!m.rows||m.rows>UINT32_MAX||!m.columns||m.columns>16384||m.columns%32)return false;
  const unsigned t=unsigned(m.type);int family=-1;
  if(dense_block_site(w,a,l))return false;
  if(iq3_block_site(w,a,l))family=0;
  else if(dense_q6_site(w,a,l)||qkv_q6_site(w,a,l)||attention_q8_site(w,a,l)||l.weights.at(0)=="output.weight")return false;
  else if(t==12||t==13||t==18||t==23||t==42)family=1;
  else if(t==8||t==14||t==20||t==21||t==22)family=2;
  else return false;
  const auto fmt=iq3::layout(iq3::Type(t));if(!fmt.elements||m.columns%fmt.elements)return false;
  if(family!=2&&t!=42&&m.columns%256)return false;
  auto& d=dev(l.card);
  if(reinterpret_cast<uintptr_t>(d.arena.row(m.x).pointer)%16||reinterpret_cast<uintptr_t>(d.arena.row(m.w).pointer)%16)return false;
  static const char* names[]{"IQ3","ELEM","KOPT"};
  const unsigned index=xgroup::config(names[family],xgroup::config_count,xgroup::default_tile(family,t));
  if(index>=xgroup::config_count)return false;
  const uint32_t rb=uint32_t(m.columns/fmt.elements*fmt.bytes),n=m.count,span=uint32_t(m.rows),k=uint32_t(m.columns);
  const std::array<Allocation,8> ids{m.w,m.x,m.y,m.routes,m.status,xg_order[c],xg_tiles[c],xg_count[c]};
  std::pair<ownrt::Event,ownrt::Event> e;
  using namespace xgroup;
  if(family==0)e=issue<S32<Iq3Words>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);
  else if(family==1){
    switch(t){
      case 12:e=issue<S32<Elem<12>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      case 13:e=issue<S32<Elem<13>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      case 18:e=issue<S32<Elem<18>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      case 23:e=issue<S32<Elem<23>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      default:e=issue<S32<Elem<42>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
    }
  } else {
    if(m.columns%8)return false;
    switch(t){
      case 8:e=issue<C8<Kopt<iq3::Type::Q8_0>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      case 14:e=issue<C8<Kopt<iq3::Type::Q6_K>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      case 20:e=issue<C8<Kopt<iq3::Type::IQ4_NL>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      case 21:e=issue<C8<Kopt<iq3::Type::IQ3_S>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
      default:e=issue<C8<Kopt<iq3::Type::IQ2_S>>,XGROUP_CONFIGS>(d,index,ids,n,m.experts,span,span,k,rb);break;
    }
  }
  finish(l.card,{e.first,e.second,2},true);
  return true;
#endif
}
void prefill_set_views(bool on) {
  for(int c=0;c<prefill_cards();++c){
  auto& d=dev(c);d.row_views.clear();d.view_row=-1;
  if(!on)continue;
  const auto& shadows=prefill_shadows[size_t(c)];const auto& bufs=buffers[size_t(c)];
  for(const auto& [name,role]:prefill_role_of)if(shadows.count(role))d.row_views[bufs.at(name).id]={shadows.at(role).id,prefill_row_bytes(c,name),false};
  d.row_views[bufs.at("position").id]={prefill_positions[size_t(c)],4,false};
  if(bufs.count("token"))d.row_views[bufs.at("token").id]={prefill_tokens[size_t(c)],4,false};
  for(const auto& [name,spare]:spares(c)){auto active=bufs.at(name).id;d.row_views[active]={spare,0,true};d.row_views[spare]={active,0,true};}
  }
}
// TP: card c's tp_route_compact over the M rows (routes of slots c, c+2, ... of every row, in row order), and the same
// slots' expert input rows for the compact gate/up launches. The input is the layer's expert_gather output.
void prefill_route_compact(const flash::Launch& l,int M) {
  const int c=l.card;require(a.tp_replicate&&l.inputs.size()==2&&l.outputs.size()==2&&l.parameter==c,"TP prefill route compact wiring");
  const uint32_t top=uint32_t(p.g.top)*uint32_t(M);
  finish(c,iq3::kopt::route_compact(dev(c),prefill_shadow(c,l.inputs[0]),prefill_shadow(c,l.inputs[1]),prefill_shadow(c,l.outputs[0]),prefill_shadow(c,l.outputs[1]),top,uint32_t(c)));
  const std::string prefix=l.inputs[0].substr(0,l.inputs[0].size()-std::string("routes").size()),x=prefix+"expert_input";
  require(ends(l.inputs[0],".routes")&&prefill_role_of.count(x),"TP prefill compact expert input: "+x);
  const size_t row=prefill_row_bytes(c,x);require(row%(size_t(p.g.top)*4)==0,"TP prefill expert input rows");
  require(dev(c).arena.row(prefill_slot_x[size_t(c)]).bytes>=size_t(M)*row/2,"TP prefill compact expert input extent");
  finish(c,iq3::kopt::slot_rows_compact(dev(c),prefill_shadow(c,x),prefill_slot_x[size_t(c)],top,uint32_t(c),uint32_t(row/(size_t(p.g.top)*4))));
}
// TP: card c's tp_xgather / tp_xheads over the M rows, as one strided direct exchange into both cards' output shadows.
// Called for card 0's site first: both cards are drained and the pair's prefill slot words zeroed on both cards. Card 0's
// half then waits on device for card 1's flag, so nothing may drain until card 1's half is issued (prefill_exchange_open:
// the chunk loop skips its periodic, profile and trace drains while it is set).
int prefill_exchange_open=-1; // card 0's exchange slot whose card-1 half is not issued yet
// OWNRT_PREFILL_XZERO_ONCE=1 (2026-10-29, research/tp/prefill-speed-2026-10-29; default off): every prefill exchange slot
// is used by exactly one pair per chunk (slot 128 + the pair's plan slot), so the chunk zeroes the counter and flag words
// of all of them once, on both cards, before its first site (the previous chunk ended drained), instead of two
// synchronous uploads and a second drain per pair. Each pair still starts with both cards drained, and each exchange's
// epoch is still 1. The decode slots are untouched.
static bool prefill_xzero_once(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_XZERO_ONCE");return e&&e[0]=='1';}();return on;}
uint32_t prefill_xzero_first=0,prefill_xzero_end=0;
void prefill_xzero_chunk() {
  namespace L=ownrt::exchange_layout;
  if(prefill_xzero_end==0){uint32_t lo=UINT32_MAX,hi=0;
    for(const auto* l:prefill_sites)if((l->op=="tp_xgather"||l->op=="tp_xheads")&&l->shape.size()>=2){const uint32_t s=prefill_exchange_slot_base+uint32_t(l->shape.at(1));lo=std::min(lo,s);hi=std::max(hi,s+1);}
    require(lo<hi&&hi<=L::slots,"TP prefill exchange slot range");prefill_xzero_first=lo;prefill_xzero_end=hi;}
  drain();const std::vector<uint8_t> zero(size_t(prefill_xzero_end-prefill_xzero_first)*L::stride*4,0);
  for(int k=0;k<2;++k)upload(k,xctl[size_t(k)],(size_t(L::header)+size_t(prefill_xzero_first)*L::stride)*4,zero.data(),zero.size());
  drain();
}
void prefill_exchange(const flash::Launch& l,int M) {
  const int c=l.card,peer=1-c;require(a.tp_replicate&&xctl.size()==2&&l.shape.size()>=2,"TP prefill exchange");
  const uint32_t slot=prefill_exchange_slot_base+uint32_t(l.shape.at(1));require(slot<ownrt::exchange_layout::slots,"TP prefill exchange slot");
  namespace L=ownrt::exchange_layout;
  require(c==0?prefill_exchange_open<0:prefill_exchange_open==int(slot),"TP prefill exchange pairing (card 0 then card 1, same slot)");
  if(c==0){drain();
    if(!prefill_xzero_once()){const std::vector<uint8_t> zero(L::stride*4,0);
      for(int k=0;k<2;++k)upload(k,xctl[size_t(k)],(size_t(L::header)+size_t(slot)*L::stride)*4,zero.data(),zero.size());
      drain();}
    else require(slot>=prefill_xzero_first&&slot<prefill_xzero_end,"TP prefill exchange slot outside the chunk's zeroed range");}
  const auto& y=buffers[size_t(c)].at(l.outputs.at(0));const size_t e=flash::scalar_bytes(y.type),row_in=prefill_row_bytes(c,l.inputs.at(0)),row_out=prefill_row_bytes(c,l.outputs.at(0));
  require(e==4&&row_in%4==0&&row_out%4==0,"TP prefill exchange rows");
  ownrt::Device::ExchangeSpec x;x.slot=slot;x.cap=tp_exchange_cap;x.control=xctl[size_t(c)];x.peer_control=xctl[size_t(peer)];x.error=buffers[size_t(c)].at("error").id;
  x.mode=0;x.src=prefill_shadow(c,l.inputs.at(0));x.bytes=row_in*size_t(M);x.local_dst=prefill_shadow(c,l.outputs.at(0));x.peer_dst=prefill_shadow(peer,l.outputs.at(0));
  if(l.op=="tp_xheads"){ // shape {global values per row, slot, run, run stride, card offset}: uniform across rows
    require(l.shape.size()==5&&l.shape[2]>0&&size_t(l.shape[0])*4==row_out&&row_in/4%size_t(l.shape[2])==0&&row_in/4/size_t(l.shape[2])*size_t(l.shape[3])*4==row_out,"TP prefill head exchange geometry"); // the run pattern continues across rows
    x.run=uint32_t(l.shape[2]);x.dst_stride=uint32_t(l.shape[3]);x.local_offset=x.peer_offset=size_t(l.shape[4])*e;
  } else { // tp_xgather: this card's half of each row (parameter values) at c*half of each R-value row
    require(l.op=="tp_xgather"&&l.inputs.at(0)!=l.outputs.at(0)&&size_t(l.shape.at(0))*4==row_out&&size_t(l.parameter)*4==row_in&&row_out==2*row_in,"TP prefill row exchange geometry");
    x.run=uint32_t(l.parameter);x.dst_stride=uint32_t(l.shape[0]);x.local_offset=x.peer_offset=size_t(c)*row_in;
  }
  auto ev=dev(c).exchange(dev(peer),x);finish(c,{ev,ev,1},false);
  prefill_exchange_open=c==0?int(slot):-1;
}
// Run rows P0..P0+M-1. rows_in: rank 1's M input stream rows (nullptr on rank 0). rows_out: M output stream rows.
void prefill_chunk(int P0,const int* tokens,int M,const uint8_t* rows_in,uint8_t* rows_out) {
  struct RetireNow{bool& flag;bool saved;~RetireNow(){flag=saved;}} retire_now_scope{retire_now,retire_now};retire_now=true; // OWNRT_RETIRE_DEFERRED: a chunk retires on the spot
  require(a.prefill_rows>0&&M>=1&&M<=a.prefill_rows,"prefill chunk rows");
  require(P0>=0&&P0+M<=p.g.context,"prefill context bound");
  // Diagnostic only (OWNRT_PREFILL_HOST_TRACE=1, 2026-10-29, research/tp/prefill-speed-2026-10-29): host-side timing of
  // the chunk (no device timing, no extra drain or wait): where the submitting thread spends its time, how long it is
  // blocked on the cards (Engine::wait), drains, exchanges and submissions per card. One line per chunk in
  // prefill-host-trace.jsonl. No arithmetic or ordering change.
  static const bool host_trace=[]{const char* e=std::getenv("OWNRT_PREFILL_HOST_TRACE");return e&&e[0]=='1';}();
  using HostClock=std::chrono::steady_clock;const auto trace_start=HostClock::now();
  const double trace_wait0=wait_ms,trace_transfer0=transfer_ms;const uint64_t trace_waits0=host_waits;const auto trace_cards0=submitted_card;
  std::map<std::string,std::array<double,3>> trace_sites; // class -> {count, host ms, of which blocked ms}
  double trace_inputs_ms=0,trace_inputs_wait=0,trace_loop_ms=0,trace_loop_wait=0,trace_final_ms=0,trace_final_wait=0;
  verify_configuration();guard();drain();
  trace_phase_begin("prefill",P0,M,0); // OWNRT_SITE_TRACE (diagnostic; no device change)
  require(integer(0,"position")==P0,"prefill position sequence");
  std::vector<int32_t> positions(M),ids(M);
  for(int r=0;r<M;++r){positions[r]=P0+r;ids[r]=tokens?tokens[r]:0;require(ids[r]>=0&&ids[r]<p.g.vocab,"prefill token bound");}
  for(int c=0;c<prefill_cards();++c){
    if(c)require(integer(c,"position")==P0,"prefill position sequence (card 1)");
    upload(c,prefill_positions[size_t(c)],0,positions.data(),size_t(M)*4);upload(c,prefill_tokens[size_t(c)],0,ids.data(),size_t(M)*4);}
  // OWNRT_PREFILL_MOE_NATIVE: the M-row ones are rewritten every chunk. A request reset zeroes every live non-weight
  // allocation and restores only the engine's one-row `one` (request_reset.hpp); build r6 wrote these once at allocation,
  // so every batched chunk after the first reset combined a zero mixture (service startup gate of 2026-10-29 server
  // tptsxqck-r1; the rank harnesses never read a prompt after a reset). Build r7; not yet device-gated.
  if(prefill_moe_native()){const std::vector<float> ones(size_t(M),1.f);
    for(int c=0;c<prefill_cards();++c)if(prefill_moe_ones[size_t(c)])upload(c,prefill_moe_ones[size_t(c)],0,ones.data(),size_t(M)*4);}
  const size_t stream=stream_bytes();
  if(rows_in){for(int c=0;c<prefill_cards();++c)upload(c,prefill_shadow(c,"streams"),0,rows_in,size_t(M)*stream);}
  else prefill_lookups(tokens,M);
  if(host_trace){trace_inputs_ms=ms(trace_start);trace_inputs_wait=wait_ms-trace_wait0;}
  if(a.tp_replicate&&prefill_xzero_once())prefill_xzero_chunk();
  const auto trace_loop_start=HostClock::now();const double trace_loop_wait0=wait_ms;
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
      if(site_trace())set_class(l->label); // OWNRT_SITE_TRACE: this site's events carry its full label
      // TP: an open exchange pair is closed by the very next site (card 1's half); no other site may come between.
      require(prefill_exchange_open<0||((l->op=="tp_xgather"||l->op=="tp_xheads")&&l->card==1),"TP prefill: card 1's exchange must follow card 0's");
      if(profile&&prefill_exchange_open<0)drain();
      const auto site_start=std::chrono::steady_clock::now();const double site_wait0=wait_ms;
      const char* trace_kind="replay";
      bool banked_native=false;
      if(l->op=="gemv"||l->op=="routed_gemv"){prefill_linear(*l,M);trace_kind="linear";}
      else if(l->op=="tp_xgather"||l->op=="tp_xheads"){prefill_exchange(*l,M);trace_kind="exchange";}
      else if(l->op=="tp_route_compact"){prefill_route_compact(*l,M);trace_kind="native";}
      else if(l->op=="moe_combine"&&prefill_moe_native()){prefill_moe_combine(*l,M);trace_kind="native";}
      else if(prefill_special_rows()&&prefill_special_row_op(l->op)){prefill_special_rows_site(*l,M);trace_kind="native";}
      else if(l->op.starts_with("tp_"))throw std::invalid_argument("TP batched prefill: unsupported site "+l->op);
      else if(prefill_native(*l)){trace_kind="native";
        if(l->op=="qsa_select"&&M>prefill_select_rows()){const int G=prefill_select_rows();for(int g=0;g<M;g+=G)prefill_native_group(*l,P0,g,std::min(G,M-g));}
        else prefill_native_site(*l,P0,M);
        banked_native=l->op=="gdn"||l->op=="conv";}
      else if(l->op=="qsa_attention"&&prefill_attention_rows()>1) {
        trace_kind="grouped";
        // Grouped rows (OWNRT_PREFILL_ATTN_ROWS=T, T<=4): one admit/tiles/combine launch set per T consecutive rows,
        // from row g's views, with the extent of the group's last row. Each row keeps its own query, ids, slot count and
        // causal bound, and combine stops at the row's own count, so its arithmetic equals its single-row replay.
        const int T=prefill_attention_rows();
        for(int g=0;g<M;g+=T) {
          const int rows=std::min(T,M-g),extent=std::min(p.g.context,((P0+g+rows-1+32)/32)*32);
          // Per-row bindings are the multi-row prefill shadows (as in prefill_native_site), each viewed at row g through
          // a temporary self-view; shared bindings (KV pools, controls) are unchanged.
          const int c=l->card;auto& d=dev(c);const int saved_extent=context_extent;context_extent=extent;
          auto site=prepare_site(*l);context_extent=saved_extent;site.spec.tokens=rows;
          std::vector<Allocation> viewed;size_t k=0;
          for(const auto* names:{&l->inputs,&l->outputs})for(const auto& name:*names){
            if(prefill_role_of.count(name)){const Allocation shadow=prefill_shadow(c,name);site.bindings.at(k)=shadow;
              require(!d.row_views.count(shadow),"prefill shadow already viewed");d.row_views[shadow]={shadow,prefill_row_bytes(c,name),false};viewed.push_back(shadow);}
            ++k;}
          d.view_row=g;
          try {finish(c,site.submit(d,site.spec,site.bindings,controls[size_t(c)],scores[size_t(c)],probabilities[size_t(c)],{}),false);}
          catch(...){d.view_row=-1;for(auto v:viewed)d.row_views.erase(v);throw;}
          d.view_row=-1;for(auto v:viewed)d.row_views.erase(v);
        }
      }
      else {
        const bool qsa=l->op=="qsa_select"||l->op=="qsa_attention";
        for(int r=0;r<M;++r) {
          // Each row's QSA sites use the context extent its own single-row step admits.
          const int extent=qsa?std::min(p.g.context,((P0+r+32)/32)*32):0;
          for(const auto& cmd:prefill_commands(*l,r,extent)){auto event=dev(l->card).issue(cmd);finish(l->card,{event,event,1},false);}
        }
      }
      // Diagnostic only (OWNRT_PREFILL_ERROR_TRACE=1): drain after every site and read every card's sticky error word,
      // so the first site that sets it is named (with the TP exchange words). Serializes the chunk; no arithmetic change.
      static const bool error_trace=[]{const char* e=std::getenv("OWNRT_PREFILL_ERROR_TRACE");return e&&e[0]=='1';}();
      if(error_trace&&prefill_exchange_open<0){drain();for(int c=0;c<prefill_cards();++c)if(integer(c,"error")){
        std::ostringstream o;o<<"prefill error trace: card "<<c<<" error after site "<<l->label<<" ("<<l->op<<", card "<<l->card<<", index "<<size_t(l-p.launches.data())<<") at P0 "<<P0<<" M "<<M;
        if(xctl.size()==2)for(int k=0;k<2;++k){auto raw=readback(k,xctl[size_t(k)],ownrt::exchange_layout::header*4);std::vector<uint32_t> w(ownrt::exchange_layout::header);std::memcpy(w.data(),raw.data(),raw.size());
          o<<"; card "<<k<<" exchange abort "<<w[ownrt::exchange_layout::abort]<<" timeouts "<<w[ownrt::exchange_layout::timeouts]<<" waits "<<w[ownrt::exchange_layout::waits]<<" max_polls "<<w[ownrt::exchange_layout::max_spin];}
        save(a.output/"prefill-error-trace.txt",o.str());throw std::runtime_error(o.str());}}
      if(host_trace){auto& t=trace_sites[std::string(trace_kind)+":"+l->op];t[0]+=1;t[1]+=ms(site_start);t[2]+=wait_ms-site_wait0;}
      if(banked_native)banks_native=true;else if(l->op=="gdn"||l->op=="conv")banks_replayed=true;
      // OWNRT_PREFILL_PROFILE_SHAPE=1 (diagnostic) also keys linear sites by their rows x columns.
      static const bool profile_shape=[]{const char* e=std::getenv("OWNRT_PREFILL_PROFILE_SHAPE");return e&&e[0]=='1';}();
      if(profile&&prefill_exchange_open<0){drain();std::string key=l->op=="gemv"||l->op=="routed_gemv"?l->op+":"+w.directory.at(l->weights.at(0)).grid:l->op;
        if(profile_shape&&(l->op=="gemv"||l->op=="routed_gemv")&&l->shape.size()==3)key+=":"+std::to_string(l->shape[1])+"x"+std::to_string(l->shape[2]);
        auto& entry=spent[key];++entry.first;entry.second+=ms(site_start);}
      // Owner event ledger holds 16384 events; retire well before it fills.
      if(submitted-drained_at>6000&&prefill_exchange_open<0){drain();drained_at=submitted;}
    }
    require(prefill_exchange_open<0,"TP prefill: chunk ended inside an exchange pair");
    prefill_set_views(false);
  } catch(...) {prefill_exchange_open=-1;prefill_set_views(false);throw;}
  if(profile){std::ofstream o(a.output/"prefill-profile.jsonl",std::ios::app);o<<"{\"position\":"<<P0<<",\"rows\":"<<M<<
#ifndef OWN_RT_HOST_ONLY
    (reuse2::enabled()?",\"chunk\":"+std::to_string(reuse2::chunk_counter()):std::string())<<
#endif
    ",\"sites\":{";bool comma=false;
    for(const auto& [k,v]:spent){o<<(comma?",":"")<<ownrt::quote(k)<<":{\"count\":"<<v.first<<",\"ms\":"<<v.second<<"}";comma=true;}o<<"}}\n";}
  if(host_trace){trace_loop_ms=ms(trace_loop_start);trace_loop_wait=wait_ms-trace_loop_wait0;}
  const auto trace_final_start=HostClock::now();const double trace_final_wait0=wait_ms;
  drain();
  for(int c=0;c<prefill_cards();++c)require(!integer(c,"error"),"sticky rank error in batched prefill");
  // Logical position follows M rows; physical bank publication depends on the recurrence path.
  const uint32_t next=uint32_t(P0+M);for(int c=0;c<prefill_cards();++c)put(c,"position",&next,4);
  // Replayed recurrences alternate banks per row (M single-row swaps); native ones leave every row in the spare bank.
  prefill_finish_banks(M,banks_native,banks_replayed);
  if(rows_out){auto raw=readback(0,prefill_shadow(0,"streams"),size_t(M)*stream);std::memcpy(rows_out,raw.data(),raw.size());}
  if(host_trace){
    trace_final_ms=ms(trace_final_start);trace_final_wait=wait_ms-trace_final_wait0;
    std::ofstream o(a.output/"prefill-host-trace.jsonl",std::ios::app);o.precision(6);
    o<<"{\"position\":"<<P0<<",\"rows\":"<<M<<",\"cards\":"<<prefill_cards()<<",\"wall_ms\":"<<ms(trace_start)
     <<",\"inputs_ms\":"<<trace_inputs_ms<<",\"inputs_blocked_ms\":"<<trace_inputs_wait<<",\"loop_ms\":"<<trace_loop_ms<<",\"loop_blocked_ms\":"<<trace_loop_wait
     <<",\"final_ms\":"<<trace_final_ms<<",\"final_blocked_ms\":"<<trace_final_wait<<",\"transfer_ms\":"<<transfer_ms-trace_transfer0
     <<",\"host_waits\":"<<host_waits-trace_waits0<<",\"submitted\":["<<submitted_card[0]-trace_cards0[0]<<","<<submitted_card[1]-trace_cards0[1]<<"]"
     <<",\"lookup_batch\":"<<(prefill_lookup_batch()?"true":"false")<<",\"sites\":{";
    bool comma=false;for(const auto& [k,v]:trace_sites){o<<(comma?",":"")<<ownrt::quote(k)<<":["<<v[0]<<","<<v[1]<<","<<v[2]<<"]";comma=true;}
    o<<"}}\n";
  }
  ++prefill_chunks;prefill_rows_done+=size_t(M);
#ifndef OWN_RT_HOST_ONLY
  ++reuse2::chunk_counter(); // OWNRT_PREFILL_REUSE2_CYCLE diagnostic: the next chunk's tile configuration
#endif
}
