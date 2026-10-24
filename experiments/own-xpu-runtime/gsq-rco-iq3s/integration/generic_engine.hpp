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
  const size_t bytes=control?count(t.shape)*4:t.bytes;
  auto id=allocate(c,"weight:"+name,bytes,Category::weights,Lifetime::process);
  weights[c][name]=id;
  for(size_t off=0;off<t.bytes;) {
    guard();size_t n=std::min(size_t(4*1024*1024),t.bytes-off);
    auto raw=w.read(name,off,n);
    if(control) {
      const auto source_width=gsq::controls::source_width(unsigned(type));
      auto upload=gsq::controls::upload_f32(unsigned(type),raw);
      this->upload(c,id,(off/source_width)*4,upload.data(),upload.size());
    } else upload(c,id,off,raw.data(),raw.size());
    off+=n;
  }
}
void gsq_linear(const flash::Launch& l) {
  const int c=l.card;
  auto it=matrices.find(&l);
  if(it==matrices.end())it=matrices.emplace(&l,std::vector<Matrix>{matrix(l)}).first;
  const auto& m=it->second.at(0);
  require(l.op=="gemv"||l.op=="routed_gemv","GSQ unfused linear operation");
  if(l.weights[0]=="output.weight"&&!a.mini) {
    require(m.type==iq3::Type::Q6_K&&variant(l)==6,"GSQ expanded head dispatch");
    finish(c,p33::submit(dev(c),{m},"p33.dense.segment",false,6),true);return;
  }
  switch(unsigned(m.type)) {
    case 12:case 13:case 18:case 23:case 42:
      finish(c,gsqn::submit(dev(c),m,l.op=="gemv"?gsqn::InputMode::shared:gsqn::InputMode::per_slot,gsqn::Storage::packed_direct),true);return;
    default:break;
  }
#ifdef OWN_RT_HOST_ONLY
  // Original Host variant0 executes the same kopt lane/tree arithmetic.
  // performance::experts would instead select variant2, so call multiply.
  finish(c,gsq_integration::host_generic(dev(c),m),true);
#else
  ownrt::Event event;
  if(l.op=="gemv")event=iq3::kopt::gemv(dev(c),m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,32);
  else event=iq3::kopt::routed_gemv(dev(c),m.type,m.w,m.x,m.y,m.routes,m.status,m.experts,m.rows,m.columns,m.count,m.rows,m.activation,m.output_type,32);
  finish(c,event);
#endif
}
