 void reset_request(const fs::path& output) {
  require(!async_pending,"reset with pending draft publication");e.drain();for(auto allocation:mutable_ids){auto bytes=e.dev(0).arena.row(allocation).bytes;
   std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)));
   for(size_t off=0;off<bytes;off+=zero.size())e.upload(0,allocation,off,zero.data(),std::min(zero.size(),bytes-off));}
  uint32_t active=1;e.upload(0,id("active"),0,&active,4);e.drain();position=0;disabled=false;reverse_hidden=nullptr;
  std::memset(e.dev(0).arena.row(publication).pointer,0,8);std::memset(e.dev(0).arena.row(half_staging).pointer,0,4+4*p.g.h*2);
  publication_event=0;e.progress_pending=false;e.progress_callback={};
  trace.close();trace.open(output/"draft-rows.jsonl");require(bool(trace),"draft reset trace");
 }
