// Exact extracted candidate Weights methods; source SHA 6a0626228caef53452aa4a48e2875f50a93df4fc26f21f971c4ed662a120a0b8
 bool lookup_view_mode=false;
  void copy_lookups(bool embedding_only=false) {
    auto start=std::chrono::steady_clock::now();uint64_t bytes=0;const size_t chunk=64ull<<20;
    for(const auto& [name,t]:directory)if(t.component=="embedding"||(!embedding_only&&t.component=="ple_lookup")) {
      std::unique_ptr<uint8_t[]> copy(new uint8_t[t.bytes]);
      for(size_t off=0;off<t.bytes;off+=chunk){size_t n=std::min(chunk,t.bytes-off);auto slice=model->slice(name,off,n);std::memcpy(copy.get()+off,slice.data(),n);}
      bytes+=t.bytes;lookup_copies.emplace(name,std::make_pair(std::move(copy),size_t(t.bytes)));
    }
    double elapsed=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    std::ostringstream o;o<<"{\"enabled\":true,\"method\":"<<ownrt::quote(embedding_only?"anonymous copy of embedding table only":"anonymous copy of embedding and PLE lookup tables")<<",\"bytes\":"<<bytes<<",\"tables\":"<<lookup_copies.size()<<",\"elapsed_ms\":"<<elapsed<<"}";residency=o.str();
  }
  void verify_lookup_views() const {
    if(lookup_view_mode)for(const auto& [name,slice]:lookup_mappings)slice->verify_backing();
  }
  void map_lookups() {
    require(!mini&&model&&lookup_copies.empty()&&lookup_mappings.empty(),"cold authenticated lookup view owner");
    const auto start=std::chrono::steady_clock::now();uint64_t bytes=0;
    for(const auto& [name,t]:directory)if(t.component=="embedding"||t.component=="ple_lookup") {
      auto slice=std::make_unique<iq3::Slice>(model->slice(name,0,t.bytes));slice->verify_backing();
      bytes+=t.bytes;lookup_mappings.emplace(name,std::move(slice));
    }
    require(lookup_mappings.size()==2,"exact first-target embedding/PLE views");lookup_view_mode=true;verify_lookup_views();
    const auto elapsed=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    std::ostringstream o;o<<"{\"enabled\":true,\"method\":\"authenticated readonly held tensor views; no advice/prefault\",\"file_backed\":true,\"guaranteed_resident\":false,\"guaranteed_pinned\":false,\"anonymous_table_bytes\":0,\"mapped_tensor_bytes\":"<<bytes<<",\"tables\":"<<lookup_mappings.size()<<",\"elapsed_ms\":"<<elapsed<<",\"identity_guard\":\"held admitted dev/ino/size/mtime/ctime before and after command result\"}";residency=o.str();
  }
  std::vector<uint8_t> read(const std::string &name, size_t off, size_t n) {
    require(n && n <= 4 * 1024 * 1024, "bounded read (4 MiB)");
    read_bytes += n;
    max_read = std::max(max_read, n);
    if (mini) {
      auto &b = synthetic.at(name);
      require(off <= b.size() && n <= b.size() - off, "synthetic bounds");
      return {b.begin() + off, b.begin() + off + n};
    }
    if(auto it=lookup_copies.find(name);it!=lookup_copies.end()) {
      require(off<=it->second.second&&n<=it->second.second-off,"lookup copy bounds");auto data=it->second.first.get()+off;return {data,data+n};
    }
    if(auto it=lookup_mappings.find(name);it!=lookup_mappings.end()) {
      require(off<=it->second->size()&&n<=it->second->size()-off,"resident lookup bounds");auto data=it->second->data()+off;return {data,data+n};
    }
    auto slice = model->slice(name, off, n);
    return {slice.data(), slice.data() + n};
  }
