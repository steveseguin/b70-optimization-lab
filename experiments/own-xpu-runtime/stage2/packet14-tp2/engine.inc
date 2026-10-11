  size_t state_elements(const std::string& name,int c,size_t full)const {
    if(ends(name,".state")){auto [lo,hi]=tp2::rows(p.g.vh,c);return full/p.g.vh*(hi-lo);}
    return full/2;
  }
  bool sharded_state(const std::string& name)const {
    return ends(name,".state") || ends(name,".history") || (p.g.kvh>1 && (ends(name,".keys") || ends(name,".values")));
  }
  std::vector<uint8_t> full_buffer(int c,const std::string& name) {
    auto slot=buffers[c].at(name);size_t bytes=slot.n*flash::scalar_bytes(slot.type);
    auto raw=readback(c,slot.id,bytes);
    if(a.cards==1 || !sharded_state(name))return raw;
    auto left=readback(0,buffers[0].at(name).id,buffers[0].at(name).n*flash::scalar_bytes(slot.type)),right=readback(1,buffers[1].at(name).id,buffers[1].at(name).n*flash::scalar_bytes(slot.type));
    std::vector<uint8_t> full;
    if(ends(name,".keys") || ends(name,".values")) {
      size_t stride=bytes/p.g.context;
      for(int t=0;t<p.g.context;++t){full.insert(full.end(),left.begin()+t*stride,left.begin()+(t+1)*stride);full.insert(full.end(),right.begin()+t*stride,right.begin()+(t+1)*stride);}
    } else {full=std::move(left);full.insert(full.end(),right.begin(),right.end());}
    return full;
  }
  struct Piece {std::string name;Allocation id;size_t width;std::vector<unsigned> slots;size_t begin=0;bool dense=false;};
  std::array<std::vector<Piece>,2> pieces;
  std::array<std::vector<Matrix>,2> prepared;
  std::array<unsigned,2> variants{};
  std::array<bool,2> expanded_dense{};
  std::array<std::vector<Allocation>,2> temporary;
  Allocation temp(int c,const std::string& name,size_t bytes) {
    auto id=allocate(c,"tp:"+name,bytes,Category::scratch,Lifetime::transaction);
    temporary[c].push_back(id);return id;
  }
  void copy_local(int c,Allocation dst,size_t offset,Allocation src,size_t source,size_t bytes) {
    ownrt::CopyEngine copy(dev(c));wait(c,copy.copy(dst,offset,src,source,bytes,{}));
    dev(c).retire_completed_events();
  }
  void peer_copy(int dst,Allocation to,size_t offset,int src,Allocation from,size_t source,size_t bytes) {
    guard();auto start=std::chrono::steady_clock::now();
    dev(dst).peer_from(dev(src),to,offset,from,source,bytes);
    dev(dst).retire_completed_events();exchange_bytes+=bytes;exchange_ms+=ms(start);
  }
  void tp_linear_rank(const flash::Launch& l) {
    int c=l.card;
    if(l.op=="gemv") {
      load(c,l.weights[0]);auto m=matrix(l);
      bool shard=a.cards==2 && l.shape[1]>=2;
      if(shard) {
        auto [lo,hi]=tp2::rows(m.rows,c);m.rows=hi-lo;m.span=m.rows;
        m.y=temp(c,l.label+":rows",m.rows*2);
        pieces[c].push_back({l.outputs[0],m.y,m.rows,{},lo,true});
      }
      auto v=arithmetic::variant(m.type,l.shape[1],l.shape[2],1,a.mini);
      if(a.cards==2){prepared[c]={m};variants[c]=v;expanded_dense[c]=tp2::expandable(m.type,l,a.mini);}
      else finish(c,tp2::dense(dev(c),m,v,tp2::expandable(m.type,l,a.mini)),true);
      return;
    }
    if(a.cards==1){linear(l);return;}
    std::vector<unsigned> slots;
    for(unsigned j=0;j<selected[c].size();++j)
      if(tp2::expert_owner(selected[c][j],p.g.experts)==c)slots.push_back(j);
    // All-on-one-card routing is valid: the other card submits no expert work.
    for(size_t i=1;i<l.outputs.size();i+=2){std::vector<uint32_t> zero(p.g.top);put(c,l.outputs[i],zero.data(),zero.size()*4);}
    if(slots.empty()){prepared[c].clear();return;}
    std::vector<Matrix> matrices;
    auto route_id=temp(c,l.label+":routes",slots.size()*sizeof(iq3::Route));
    std::vector<iq3::Route> routes;
    for(unsigned j=0;j<slots.size();++j)routes.push_back({j,0,uint32_t(l.shape[1])});
    upload(c,route_id,0,routes.data(),routes.size()*sizeof(iq3::Route));
    Allocation input=buffers[c].at(l.inputs[0]).id;
    bool shared=l.op=="expert_gate_up";
    if(!shared) {
      input=temp(c,l.label+":x",slots.size()*l.shape[2]*2);
      for(unsigned j=0;j<slots.size();++j)copy_local(c,input,j*l.shape[2]*2,buffers[c].at(l.inputs[0]).id,slots[j]*l.shape[2]*2,l.shape[2]*2);
    }
    for(size_t projection=0;projection<l.weights.size();++projection) {
      const auto& name=l.weights[projection];const auto& t=w.directory.at(name);
      size_t eb=t.bytes/p.g.experts;
      if(!weights[c].count(name)) {
        auto id=allocate(c,"selected:"+name,eb*slots.size(),Category::weights,Lifetime::process);
        weights[c][name]=id;
        for(unsigned j=0;j<slots.size();++j)for(size_t off=0;off<eb;off+=4*1024*1024) {
          auto bytes=w.read(name,selected[c][slots[j]]*eb+off,std::min(eb-off,size_t(4*1024*1024)));
          upload(c,id,j*eb+off,bytes.data(),bytes.size());
        }
      }
      Matrix m{};m.type=flash::grid_type(t.grid);m.w=weights[c].at(name);m.x=input;
      m.rows=l.shape[1];m.columns=l.shape[2];m.span=m.rows;m.count=slots.size();m.experts=slots.size();
      m.y=temp(c,l.label+":y"+std::to_string(projection),slots.size()*m.rows*2);
      m.status=temp(c,l.label+":status"+std::to_string(projection),slots.size()*4);
      m.routes=route_id;m.workspace=workspace[c];matrices.push_back(m);
      pieces[c].push_back({l.outputs[projection*2],m.y,m.rows,slots,0,false});
    }
    prepared[c]=std::move(matrices);
  }
  flash::Event enqueue(const flash::Launch& launch,flash::Event dep)override {
    require(dep==logical,"TP logical event order");
    double old_exchange=exchange_ms;auto old_bytes=exchange_bytes;
    bool parallel=a.cards==2 && (launch.op=="gemv" || launch.op=="routed_gemv" || launch.op=="expert_gate_up");
    if(parallel) {
      guard();
      for(int c=0;c<2;++c){if(launch.label.starts_with("blk."))stage_layer(c,std::stoi(launch.label.substr(4)));auto l=launch;l.card=c;tp_linear_rank(l);}
      std::array<Launch,2> pending{};
      std::array<std::chrono::steady_clock::time_point,2> started;
      for(int c=0;c<2;++c)if(!prepared[c].empty()) {
        started[c]=std::chrono::steady_clock::now();
        pending[c]=launch.op=="gemv"?tp2::dense(dev(c),prepared[c][0],variants[c],expanded_dense[c]):tp2::experts(dev(c),prepared[c],launch.op=="expert_gate_up");
      }
      for(int c=0;c<2;++c)if(!prepared[c].empty()) {
        auto old_g=gemv_ms;finish(c,pending[c],true);
        timings<<"{\"kind\":\"rank_site\",\"label\":"<<ownrt::quote(launch.label)<<",\"card\":"<<c
          <<",\"wall_ms\":"<<ms(started[c])<<",\"gemv_device_ms\":"<<device_ms(gemv_ms-old_g)<<",\"non_gemv_device_ms\":"<<device_ms(0)<<"}\n";
        if(launch.op!="gemv")for(auto m:prepared[c]){auto status=readback(c,m.status,m.count*4);require(std::all_of(status.begin(),status.end(),[](auto b){return b==0;}),"local expert status");}
        require(!integer(c,"error"),"rank sticky error");
      }
      ++logical;
    } else for(int c=0;c<a.cards;++c) {
      auto l=launch;l.card=c;auto start=std::chrono::steady_clock::now();auto old_g=gemv_ms;auto old_n=nongemv_ms;
      enqueue_rank(l,logical);
      timings<<"{\"kind\":\"rank_site\",\"label\":"<<ownrt::quote(l.label)<<",\"card\":"<<c
        <<",\"wall_ms\":"<<ms(start)<<",\"gemv_device_ms\":"<<device_ms(gemv_ms-old_g)
        <<",\"non_gemv_device_ms\":"<<device_ms(nongemv_ms-old_n)<<"}\n";
    }
    if(a.cards==2) {
      if(launch.op=="conv" || launch.op=="gdn" || launch.op=="qsa_attention") {
        const auto& name=launch.outputs[0];size_t elements=buffers[0].at(name).n;
        for(int c=0;c<2;++c) {
          auto [lo,hi]=tp2::rows(launch.op=="gdn"?p.g.vh:elements,c);
          size_t stride=launch.op=="gdn"?p.g.d:1,offset=lo*stride*2,bytes=(hi-lo)*stride*2;
          peer_copy(1-c,buffers[1-c].at(name).id,offset,c,buffers[c].at(name).id,offset,bytes);
        }
      }
      // Replicated router math must agree before either rank reads expert bytes.
      if(launch.op=="route")for(const auto& name:launch.outputs) {
        auto slot=buffers[0].at(name);size_t bytes=slot.n*flash::scalar_bytes(slot.type);
        require(readback(0,slot.id,bytes)==readback(1,buffers[1].at(name).id,bytes),"route agreement failed");
      }
      for(int c=0;c<2;++c)for(const auto& piece:pieces[c]) {
        if(piece.dense) {
          copy_local(c,buffers[c].at(piece.name).id,piece.begin*2,piece.id,0,piece.width*2);
          peer_copy(1-c,buffers[1-c].at(piece.name).id,piece.begin*2,c,piece.id,0,piece.width*2);
        } else {
          auto received=temp(1-c,"recv:"+piece.name,piece.slots.size()*piece.width*2);
          peer_copy(1-c,received,0,c,piece.id,0,piece.slots.size()*piece.width*2);
          for(unsigned j=0;j<piece.slots.size();++j) {
            size_t offset=piece.slots[j]*piece.width*2,source=j*piece.width*2,bytes=piece.width*2;
            copy_local(c,buffers[c].at(piece.name).id,offset,piece.id,source,bytes);
            copy_local(1-c,buffers[1-c].at(piece.name).id,offset,received,source,bytes);
          }
        }
      }
      for(int c=0;c<2;++c){for(auto id:temporary[c])dev(c).arena.release(id);temporary[c].clear();pieces[c].clear();}
      if(ends(launch.label,".ffn.combine")) {
        auto n=buffers[0].at("streams").n*2;
        require(readback(0,buffers[0].at("streams").id,n)==readback(1,buffers[1].at("streams").id,n),"rank hidden mismatch");
      }
    }
    timings<<"{\"kind\":\"exchange_site\",\"label\":"<<ownrt::quote(launch.label)
      <<",\"bytes\":"<<exchange_bytes-old_bytes<<",\"wall_ms\":"<<exchange_ms-old_exchange<<"}\n";
    return logical;
  }
