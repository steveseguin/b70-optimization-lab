  void warm_lookups(){throw std::runtime_error("two-rank lookup warming is unavailable in one-card packet58t");}
  std::map<std::string,std::unique_ptr<p58t::ResidentLookup>> resident_lookups;
  bool use_resident_lookups=false;
  void load_resident_lookups() {
    require(resident_lookups.empty(),"resident lookups loaded twice");
    uint64_t total=0;std::ostringstream rows;bool comma=false;
    auto start=std::chrono::steady_clock::now();
    for(const char* key:{"token_embd.weight","per_layer_token_embd.weight"}) {
      auto it=directory.find(key);require(it!=directory.end(),"required lookup tensor absent");
      const auto& t=it->second;total+=t.bytes;
      require(mini||total<=29321610240ull,"resident lookup admission bytes exceeded");
      auto copy=std::make_unique<p58t::ResidentLookup>(t.bytes,
        [&](size_t off,size_t n){return read(key,off,n);},
        []{require(!stopped,"stopped during lookup load");});
      rows<<(comma?",":"")<<"{\"name\":"<<ownrt::quote(key)<<",\"bytes\":"<<t.bytes
          <<",\"source_sha256\":"<<ownrt::quote(copy->source_sha256)
          <<",\"resident_sha256\":"<<ownrt::quote(copy->resident_sha256)<<"}";
      comma=true;resident_lookups.emplace(key,std::move(copy));
    }
    require(mini||total==29321610240ull,"resident lookup model size differs");
    residency="{\"enabled\":true,\"method\":\"anonymous packed copy at load, SHA256 verified, read-only\",\"guaranteed_pinned\":false,\"bytes\":"+
      std::to_string(total)+",\"load_ms\":"+std::to_string(std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count())+
      ",\"tensors\":["+rows.str()+"]}";
  }
