
  // CPU-only real-model chain adapter. The original GEMV produces its exact
  // stored bytes, then these packet39 scalar epilogues execute at that site.
  // The superseded logical sites remain no-ops to retain layer-fixture hooks.
  uint64_t p39_rows=0,p39_removed=0;
  void* p39_pointer(int c,const std::string& name) {return dev(c).arena.row(buffers[c].at(name).id).pointer;}
  bool p39_skip(const flash::Launch& l) {
    const auto s=packet26::Dispatch::class_name(l.label);
    const bool skip=s=="gdn.conv"||s=="expsgate.check"||s=="expsup.check"||s=="expsdown.check"||s=="expsact"||s=="shexpact"||s=="hc.a.act"||s=="hc.f.act"||s=="final.act"||s=="attn.combine"||s=="ffn.combine"||s=="moe"||s=="shared_gate";
    if(skip)++p39_removed;
    return skip;
  }
  void p39_after(const flash::Launch& l) {
    const int c=l.card;const auto s=packet26::Dispatch::class_name(l.label);
    auto u=[&](const std::string& name){return static_cast<uint16_t*>(p39_pointer(c,name));};
    auto word=[&](const std::string& name){return static_cast<uint32_t*>(p39_pointer(c,name));};
    const std::string prefix=l.label.substr(0,l.label.size()-s.size());
    p39::Bound b;b.rows=unsigned(l.shape[1]);b.count=unsigned(l.shape[0]);b.y=u(l.outputs[0]);b.error=word("error");b.active=word("active");b.position=word("position");b.capacity=p.g.context;
    if(s=="gdn.qkv") {
      b.history=u(prefix+"gdn.history");b.out=u(prefix+"gdn.conv");const auto name=prefix+"ssm_conv1d.weight";load(c,name);b.conv_weights=static_cast<float*>(dev(c).arena.row(weights[c].at(name)).pointer);
      require(flash::grid_type(w.directory.at(name).grid)==iq3::Type::F32,"packet39 convolution F32 weights");p39::host_tail<p39::Kind::gdn_conv>(b);p39_rows+=b.rows;
    } else if(s=="expsgate") {
      b.py=u(l.outputs[2]);b.status=word(l.outputs[1]);b.peer_status=word(l.outputs[3]);b.out=u(prefix+"expsact");
      p39::host_tail<p39::Kind::expert_act>(b);p39_rows+=uint64_t(b.rows)*b.count;
    } else if(s=="expsdown") {
      b.status=word(l.outputs[1]);p39::host_tail<p39::Kind::down_status>(b);
      // Existing unconditional ordered mixture moves earlier; no reduction
      // arithmetic is inserted into a GEMV epilogue.
      finish(c,mixture(dev(c),buffers[c].at(l.outputs[0]).id,buffers[c].at(prefix+"prob").id,mixture_out[c],p.g.h),false);
      const flash::Launch* scalar=nullptr;for(const auto& site:p.launches)if(site.label==prefix+"shared_gate")scalar=&site;
      require(scalar,"packet39 shared scalar plan site");linear(*scalar);
    } else if(s=="hc.a.low"||s=="hc.f.low"||s=="final.low") {
      b.out=u(l.label.substr(0,l.label.size()-3)+"act");p39::host_tail<p39::Kind::silu_div4>(b);p39_rows+=b.rows;
    } else if(s=="shexpup") {
      b.other=u(prefix+"shexpgate");b.out=u(prefix+"shexpact");p39::host_tail<p39::Kind::shared_act>(b);p39_rows+=b.rows;
    } else if(s=="attention") {
      b.streams=u("streams");b.inject=u(prefix+"hc.a.inject");p39::host_tail<p39::Kind::attention_combine>(b);p39_rows+=b.rows;
    } else if(s=="shexpdown") {
      b.streams=u("streams");b.inject=u(prefix+"hc.f.inject");b.shared_gate=u(prefix+"shared_gate");b.mixture=static_cast<uint16_t*>(dev(c).arena.row(mixture_out[c]).pointer);b.out=u(prefix+"moe");
      p39::host_tail<p39::Kind::shared_combine>(b);p39_rows+=b.rows;
    }
  }
