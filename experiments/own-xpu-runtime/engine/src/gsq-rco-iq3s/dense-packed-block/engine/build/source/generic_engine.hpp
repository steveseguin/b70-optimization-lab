// Included inside the authentic Engine definition by prepare.py.
// Direct packed target arithmetic; the full expanded Q6 head is explicit.
bool gsq_control(const std::string& name) const {
  return gsq_integration::control_names.contains(name);
}
void gsq_load(int c, const std::string& name) {
  const auto& t=w.directory.at(name);
  require(t.component!="embedding"&&t.component!="ple_lookup","GSQ lookup is row bounded");
  if(name=="output.weight" && !a.mini) {
    // Delegate exactly this one admitted storage exception to inherited load.
    require(flash::grid_type(t.grid)==iq3::Type::Q6_K&&t.shape==std::vector<int>({248320,2560}),"GSQ full Q6 head");
    return;
  }
  const bool control=gsq_control(name);
  const auto type=flash::grid_type(t.grid);
  // TP rows: whole rows of a row-major tensor (row bytes = bytes / rows), uploaded in run order. A row split
  // (2026-10-25) has one run of a raw 2-D tensor; a head split (2026-10-28) may also slice control tensors (ssm_a,
  // ssm_dt.bias, ssm_conv1d), whose F32 conversion is per element and so unchanged by the slice.
  const auto runs=tp_runs(c,name);
  require(runs.empty()||(!t.shape.empty()&&t.bytes%size_t(t.shape[0])==0&&(t.shape.size()==2||(control&&t.shape.size()==1))),"TP rows: row-major tensor rows only");
  const size_t row_bytes=t.shape.empty()?0:t.bytes/size_t(t.shape[0]);
  size_t total=t.bytes;if(!runs.empty()){total=0;for(auto [first,rows]:runs){require(first+rows<=size_t(t.shape[0]),"TP row run bound");total+=rows*row_bytes;}}
  const size_t bytes=control?(runs.empty()?count(t.shape)*4:(count(t.shape)/size_t(t.shape[0]))*(total/row_bytes)*4):total;
  auto id=allocate(c,"weight:"+name,bytes,Category::weights,Lifetime::process);
  weights[c][name]=id;
  const std::vector<std::pair<size_t,size_t>> spans=runs.empty()?std::vector<std::pair<size_t,size_t>>{{0,t.bytes}}:[&]{std::vector<std::pair<size_t,size_t>> v;for(auto [first,rows]:runs)v.push_back({first*row_bytes,rows*row_bytes});return v;}();
  size_t done=0; // destination offset in source bytes
  for(auto [begin,length]:spans)for(size_t off=0;off<length;) {
    guard();size_t n=std::min(size_t(4*1024*1024),length-off);
    auto raw=w.read(name,begin+off,n);
    if(control) {
      const auto source_width=gsq::controls::source_width(unsigned(type));
      require((done+off)%source_width==0&&n%source_width==0,"control rows split on element boundaries");
      auto upload=gsq::controls::upload_f32(unsigned(type),raw);
      this->upload(c,id,((done+off)/source_width)*4,upload.data(),upload.size());
    } else upload(c,id,done+off,raw.data(),raw.size());
    off+=n;if(off==length)done+=length;
  }
}
// Sibling fusion (single-row steps): two plan sites that read the same input and run on the kopt GEMV with one weight
// type are issued as one launch at the first site; the second site then issues nothing. Each row keeps its
// single-matrix arithmetic and writes its own output. Pairs: HC low+inject, GDN a+b, indexer q+k, router+shared gate.
// The few-row member was memory-latency bound on its own (HC inject 4x10240: 52.7 us, the same as 320-row HC low).
// OWNRT_DECODE_FUSE=0 turns it off.
std::unordered_map<const flash::Launch*,const flash::Launch*> gsq_partner;
std::unordered_set<const flash::Launch*> gsq_follower;
std::unordered_map<const flash::Launch*,const flash::Launch*> gsq_mix_partner;
std::unordered_set<const flash::Launch*> gsq_mix_follower;
// OWNRT_TP_EXPERT_PAIR=1 (2026-10-30, research/tp/fixed-cost-2026-10-30; decode only, expert_pair.hpp): a layer's routed
// gate and up GEMVs and their SiLU product run as one launch at the gate site; the up and activation sites then issue
// nothing in decode (row replays, dev.view_row >= 0, and batched prefill keep the three sites). family 0: kopt
// MultiplyBlockRows (IQ2_S, IQ3_S); family 1: XxsDn2 (IQ3_XXS block sites). Any other layer stays unpaired.
struct ExpertPair {const flash::Launch* up;const flash::Launch* act;int family;};
std::unordered_map<const flash::Launch*,ExpertPair> expert_pair_of;
std::unordered_set<const flash::Launch*> expert_pair_follower; // up (gsq_linear) and act (execute_site)
bool gsq_fusion_ready=false;
bool gsq_kopt_site(const flash::Launch& l) const {
  if(l.op!="gemv"||dense_block_site(w,a,l)||iq3_block_site(w,a,l)||dense_q6_site(w,a,l)||qkv_q6_site(w,a,l)||attention_q8_site(w,a,l)||l.weights.at(0)=="output.weight")return false;
  const auto t=unsigned(flash::grid_type(w.directory.at(l.weights.at(0)).grid));
  return !(t==12||t==13||t==18||t==23||t==42); // gsqn types take the packed kernel instead
}
void gsq_prepare_fusion() {
  gsq_fusion_ready=true;
#ifdef OWN_RT_HOST_ONLY
  return; // the host build has no fused kopt launch; every site computes its own rows
#endif
  static const bool enabled=[]{const char* e=std::getenv("OWNRT_DECODE_FUSE");return !e||e[0]!='0';}();
  if(!enabled||a.mini)return;
  static const std::array<std::pair<const char*,const char*>,5> pairs{{{".hc.a.low",".hc.a.inject"},{".hc.f.low",".hc.f.inject"},{".gdn.a",".gdn.b"},{".qsa.iq",".qsa.ik"},{"router","shared_gate"}}};
  // Keyed by label and card: under --tp-replicate every label exists once per card, and pairs never cross cards.
  std::map<std::string,const flash::Launch*> by_label;for(const auto& l:p.launches)by_label[l.label+"@"+std::to_string(l.card)]=&l;
  for(size_t i=0;i<p.launches.size();++i) {
    const auto& first=p.launches[i];if(!first.label.starts_with("blk."))continue;
    for(const auto& [x,y]:pairs) {
      if(!ends(first.label,x))continue;
      auto found=by_label.find(first.label.substr(0,first.label.size()-std::strlen(x))+y+"@"+std::to_string(first.card));if(found==by_label.end())continue;
      const auto& second=*found->second;size_t j=size_t(&second-p.launches.data());
      if(j<=i||second.inputs.at(0)!=first.inputs.at(0)||!gsq_kopt_site(first)||!gsq_kopt_site(second))continue;
      if(w.directory.at(first.weights.at(0)).grid!=w.directory.at(second.weights.at(0)).grid)continue;
      bool written=false;for(size_t k=i+1;k<j&&!written;++k)if(p.launches[k].card==first.card)for(const auto& out:p.launches[k].outputs)written|=out==first.inputs.at(0);
      if(written)continue;
      gsq_partner[&first]=&second;gsq_follower.insert(&second);
    }
  }
  // HC gate + mix (OWNRT_FUSE_MIX=1): the gate GEMV (4*width rows) also writes its hc_mix output; the mix site then
  // issues nothing in decode. Prefill runs both sites unfused (gsq_linear_matrix and row replays).
  static const bool mix_enabled=[]{const char* e=std::getenv("OWNRT_FUSE_MIX");return e&&e[0]=='1';}();
  if(mix_enabled&&a.f32_activations)for(size_t i=0;i<p.launches.size();++i) {
    const auto& gate=p.launches[i];
    if(gate.op!="gemv"||!(ends(gate.label,".hc.a.gate")||ends(gate.label,".hc.f.gate"))||!gsq_kopt_site(gate)||gsq_partner.count(&gate)||gsq_follower.count(&gate))continue;
    auto found=by_label.find(gate.label.substr(0,gate.label.size()-4)+"mix@"+std::to_string(gate.card));if(found==by_label.end())continue;
    const auto& mix=*found->second;const size_t j=size_t(&mix-p.launches.data());
    if(j<=i||mix.op!="hc_mix"||mix.card!=gate.card||mix.inputs.size()<2||mix.inputs.at(1)!=gate.outputs.at(0)||mix.outputs.size()!=1)continue;
    if(gate.shape.size()<3||mix.shape.size()<2||size_t(gate.shape[1])!=size_t(mix.shape[1])*4)continue;
    bool written=false;for(size_t k=i+1;k<j&&!written;++k)if(p.launches[k].card==gate.card)for(const auto& out:p.launches[k].outputs)written|=out==mix.inputs.at(0)||out==gate.outputs.at(0);
    if(written)continue;
    gsq_mix_partner[&gate]=&mix;gsq_mix_follower.insert(&mix);
  }
  if(expert_pair::enabled()&&a.f32_activations&&a.memory=="resident"&&experts_v2::enabled("ew"))for(size_t i=0;i<p.launches.size();++i) {
    const auto& gate=p.launches[i];
    if(gate.op!="routed_gemv"||!gate.label.starts_with("blk.")||!ends(gate.label,".expsgate")||gate.inputs.size()<2||gate.outputs.size()<2)continue;
    const std::string prefix=gate.label.substr(0,gate.label.size()-8),card="@"+std::to_string(gate.card);
    auto up_it=by_label.find(prefix+"expsup"+card),act_it=by_label.find(prefix+"expsact"+card);
    if(up_it==by_label.end()||act_it==by_label.end())continue;
    const auto& up=*up_it->second;const auto& act=*act_it->second;
    const size_t j=size_t(&up-p.launches.data()),k=size_t(&act-p.launches.data());
    if(!(i<j&&j<k)||up.op!="routed_gemv"||act.op!="silu_product"||up.card!=gate.card||act.card!=gate.card)continue;
    if(up.slots!=gate.slots||act.slots!=gate.slots||up.inputs.size()<2||up.outputs.size()<2||act.inputs.size()<2||act.outputs.size()!=1)continue;
    if(up.inputs[0]!=gate.inputs[0]||up.inputs[1]!=gate.inputs[1]||act.inputs[0]!=gate.outputs[0]||act.inputs[1]!=up.outputs[0])continue;
    bool other=false;for(size_t q=i+1;q<k&&!other;++q)if(q!=j&&p.launches[q].card==gate.card)other=true; // nothing else of this card in between
    if(other)continue;
    const auto& tg=w.directory.at(gate.weights.at(0));const auto& tu=w.directory.at(up.weights.at(0));
    if(tg.grid!=tu.grid)continue;
    const auto t=flash::grid_type(tg.grid);int family=-1;
    if(iq3_block_site(w,a,gate)&&iq3_block_site(w,a,up))family=1;
    else if(!dense_block_site(w,a,gate)&&!dense_block_site(w,a,up)&&(t==iq3::Type::IQ2_S||t==iq3::Type::IQ3_S)&&
            iq3::kopt::routed_pairs(t,size_t(gate.shape.at(2)),uint32_t(gate.slots?gate.slots:p.g.top),iq3::Type::F32,iq3::Type::F32,32,0))family=0;
    if(family<0)continue;
    expert_pair_of[&gate]=ExpertPair{&up,&act,family};expert_pair_follower.insert(&up);expert_pair_follower.insert(&act);
  }
  save(a.output/"decode-fusion.json","{\"pairs\":"+std::to_string(gsq_partner.size())+",\"gate_mix\":"+std::to_string(gsq_mix_partner.size())+",\"expert_pairs\":"+std::to_string(expert_pair_of.size())+"}");
}
void gsq_linear(const flash::Launch& l) {
  if(!gsq_fusion_ready)gsq_prepare_fusion();
  if(gsq_follower.count(&l))return; // written by its fused sibling's launch
  if(dev(l.card).view_row<0) { // OWNRT_TP_EXPERT_PAIR (decode only)
    if(expert_pair_follower.count(&l))return; // the up GEMV: written by its gate's paired launch
    if(auto pr=expert_pair_of.find(&l);pr!=expert_pair_of.end()){gsq_expert_pair(l,pr->second);return;}
  }
  auto it=matrices.find(&l);
  if(it==matrices.end())it=matrices.emplace(&l,std::vector<Matrix>{matrix(l)}).first;
#ifndef OWN_RT_HOST_ONLY
  if(auto partner=gsq_partner.find(&l);partner!=gsq_partner.end()) {
    auto other=matrices.find(partner->second);
    if(other==matrices.end())other=matrices.emplace(partner->second,std::vector<Matrix>{matrix(*partner->second)}).first;
    const auto& m=it->second.at(0);const auto& n=other->second.at(0);
    require(m.tokens==1&&n.tokens==1&&m.x==n.x&&m.type==n.type,"fused sibling matrices");
    std::vector<iq3::kopt::Matrix> pair{{m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,0},{n.type,n.w,n.x,n.y,n.rows,n.columns,n.activation,n.output_type,0}};
    finish(l.card,iq3::kopt::fused_gemv(dev(l.card),pair,32));return;
  }
  if(auto mixed=gsq_mix_partner.find(&l);mixed!=gsq_mix_partner.end()) {
    const auto& m=it->second.at(0);const auto& mix=*mixed->second;const int c=l.card;
    require(m.tokens==1&&m.rows==size_t(mix.shape[1])*4,"fused gate+mix matrix");
    finish(c,iq3::kopt::gemv_mix(dev(c),m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,32,
      buffers[c].at(mix.inputs.at(0)).id,buffers[c].at(mix.outputs.at(0)).id,uint32_t(mix.shape[1])));return;
  }
#endif
  gsq_linear_matrix(l,it->second.at(0));
}
// OWNRT_TP_EXPERT_PAIR: the gate site's paired launch (gate, up, act = silu(gate) * up) with the activation site's own
// output and guard bindings (its prepared ng bindings: inputs gate y, up y (then active, error), output, then scratch,
// error, position, active: adapter.cpp a[15], a[17], a[18]).
void gsq_expert_pair(const flash::Launch& g,const ExpertPair& pr) {
  const int c=g.card;const auto& u=*pr.up;
  auto mg_it=matrices.find(&g);if(mg_it==matrices.end())mg_it=matrices.emplace(&g,std::vector<Matrix>{matrix(g)}).first;
  auto mu_it=matrices.find(&u);if(mu_it==matrices.end())mu_it=matrices.emplace(&u,std::vector<Matrix>{matrix(u)}).first;
  const Matrix& mg=mg_it->second.at(0);const Matrix& mu=mu_it->second.at(0);
  const auto& pa=prepared.at(pr.act);const size_t base=size_t(pa.spec.ni+pa.spec.no+pa.spec.nw);
  require(pa.spec.ni>=2&&pa.spec.no==1&&pa.spec.nw==0&&pa.bindings.size()>base+3&&pa.spec.f32_activations&&pa.spec.tokens==1,"expert pair: activation binding shape (ni "+std::to_string(pa.spec.ni)+
          " no "+std::to_string(pa.spec.no)+" nw "+std::to_string(pa.spec.nw)+" bindings "+std::to_string(pa.bindings.size())+" f32 "+std::to_string(pa.spec.f32_activations)+" tokens "+std::to_string(pa.spec.tokens)+")");
  require(pa.bindings[0]==mg.y&&pa.bindings[1]==mu.y&&pa.spec.sizes[0]==mg.count*mg.rows&&mg.tokens==1&&mu.tokens==1,"expert pair: the activation reads this pair's outputs");
  require(mg.type==mu.type&&mg.x==mu.x&&mg.routes==mu.routes&&mg.count==mu.count&&mg.rows==mu.rows&&mg.columns==mu.columns&&mg.span==mu.span&&mg.experts==mu.experts,"expert pair: matching gate/up matrices");
  const ownrt::Allocation act=pa.bindings[size_t(pa.spec.ni)],error=pa.bindings[base+1],position=pa.bindings[base+2],active=pa.bindings[base+3]; // ng out(2,0) = bindings[ni]
  const int limit=pa.spec.g.context-pa.spec.tokens; // ng position_limit(activation) = capacity = g.context
  if(pr.family==1){finish(c,iq3block::submit_pair(dev(c),mg,mu,g.label,g.weights.at(0),u.label,u.weights.at(0),act,active,error,position,limit),true);return;}
  finish(c,iq3::kopt::routed_pair(dev(c),mg.type,mg.w,mu.w,mg.x,mg.y,mu.y,mg.routes,mg.status,mu.status,uint32_t(mg.experts),uint32_t(mg.rows),mg.columns,
                                  uint32_t(mg.count),uint32_t(mg.span),act,active,error,position,limit));
}
// One site-selected dispatch for a single row (m.tokens==1, m.count = expert slots) and for batched prefill rows
// (dense: m.tokens rows of per-slot input; routed: m.count = rows*top slots). Kernel choice, weights and per-row
// arithmetic are the same in both cases.
void gsq_linear_matrix(const flash::Launch& l,const Matrix& m) {
  const int c=l.card;
  require(l.op=="gemv"||l.op=="routed_gemv","GSQ unfused linear operation");
  const auto dense_input=m.tokens>1?gsqn::InputMode::per_slot:gsqn::InputMode::shared;
  if(dense_block_site(w,a,l)){const auto*s=denseblock::selected(l.label,l.weights.at(0));require(s&&variant(l)==0&&dev(c).arena.row(m.w).bytes==(l.row_count?size_t(l.row_count)*(s->bytes/s->rows):s->bytes),"dense block raw storage/variant");finish(c,denseblock::submit(dev(c),m,l.label,l.weights.at(0),dense_input,size_t(l.row_count)),true);return;}
  if(iq3_block_site(w,a,l)){require(((m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16)||(m.activation==iq3::Type::F32&&m.output_type==iq3::Type::F32))&&!m.fp32&&dev(c).arena.row(m.w).bytes==321126400,"IQ3 block exact matrix storage");finish(c,iq3block::submit(dev(c),m,l.label,l.weights.at(0),gsqn::InputMode::per_slot,l.slots!=0),true);return;}
  if(dense_q6_site(w,a,l)){dense_q6_matrix(m,l,variant(l),dev(c).arena.row(m.w).bytes);finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;}
  if(qkv_q6_site(w,a,l)){require(m.type==iq3::Type::Q6_K&&m.rows==(l.row_count?size_t(l.row_count):10240)&&m.columns==2560&&variant(l)==6&&((m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16)||(m.activation==iq3::Type::F32&&m.output_type==iq3::Type::F32))&&!m.fp32&&!m.routes&&!m.status&&m.count==1&&m.experts==1&&(m.span==0||m.span==m.rows)&&dev(c).arena.row(m.w).bytes==(l.row_count?size_t(l.row_count)*(m.raw?2100:3380):(m.raw?21504000:34611200)),"QKV Q6 variant6 only");finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;}
  if(attention_q8_site(w,a,l)){require(m.type==iq3::Type::Q8_0&&m.rows==(l.row_count?size_t(l.row_count):2560)&&m.columns==6144&&variant(l)==6&&((m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16)||(m.activation==iq3::Type::F32&&m.output_type==iq3::Type::F32))&&!m.fp32&&!m.routes&&!m.status&&m.count==1&&m.experts==1&&(m.span==0||m.span==m.rows)&&dev(c).arena.row(m.w).bytes==(l.row_count?size_t(l.row_count)*(m.raw?6528:7296):(m.raw?16711680:18677760)),"attention Q8 variant6 only");finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;}
  if(l.weights[0]=="output.weight"&&!a.mini) {
    require(m.type==iq3::Type::Q6_K&&variant(l)==6,"GSQ expanded head dispatch");
    finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;
  }
  switch(unsigned(m.type)) {
    case 12:case 13:case 18:case 23:case 42:
      finish(c,gsqn::submit(dev(c),m,l.op=="gemv"?dense_input:gsqn::InputMode::per_slot,gsqn::Storage::packed_direct),true);return;
    default:break;
  }
#ifdef OWN_RT_HOST_ONLY
  // Original Host variant0 executes the same kopt lane/tree arithmetic.
  // performance::experts would instead select variant2, so call multiply.
  require(m.tokens==1,"GSQ host generic: one token row");
  finish(c,gsq_integration::host_generic(dev(c),m),true);
#else
  ownrt::Event event;
  if(l.op=="gemv")event=m.tokens>1?iq3::kopt::gemv_tokens(dev(c),m.type,m.w,m.x,m.y,m.rows,m.columns,m.tokens,m.activation,m.output_type,32):iq3::kopt::gemv(dev(c),m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,32);
  else event=iq3::kopt::routed_gemv(dev(c),m.type,m.w,m.x,m.y,m.routes,m.status,m.experts,m.rows,m.columns,m.count,m.rows,m.activation,m.output_type,32);
  finish(c,event);
#endif
}
