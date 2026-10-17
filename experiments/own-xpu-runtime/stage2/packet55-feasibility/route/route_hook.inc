  // Packet55 diagnostic: no device arithmetic or dispatch change. This copy
  // follows router completion and the site's profiling interval. Whole-request
  // timings now include instrumentation and MUST NOT be used as speed results.
  std::ofstream p55_routes;
  fs::path p55_route_path;
  uint64_t p55_sequence=0;
  uint32_t p55_command=0,p55_speculative=0,p55_fixture=0;
  void p55_route(int card,int position,int layer,bool draft,Allocation ids,
                 Allocation probability,unsigned count) {
    require(count<=10 && position>=0 && layer>=0,"p55 route dimensions");
    auto dest=a.output/"routes.p55bin";
    if(dest!=p55_route_path){
      p55_routes.close();p55_routes.clear();
      require(!fs::exists(dest),"p55 route output already exists");
      p55_routes.open(dest,std::ios::binary);p55_route_path=dest;
      p55_routes.write("P55RTE1\n",8);
    }
    auto id_bytes=readback(card,ids,count*4);
    auto weight_bytes=readback(card,probability,count*4);
    uint64_t prefix[2]={p55_sequence++,uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count())};
    uint32_t fields[7]={uint32_t(position),uint32_t(layer),uint32_t(draft),count,p55_command,p55_speculative,p55_fixture};
    uint32_t expert[10]{};float weight[10]{};
    std::memcpy(expert,id_bytes.data(),count*4);std::memcpy(weight,weight_bytes.data(),count*4);
    for(unsigned i=0;i<count;++i){require(expert[i]<unsigned(p.g.experts)&&std::isfinite(weight[i])&&weight[i]>=0,"p55 invalid route");for(unsigned j=0;j<i;++j)require(expert[i]!=expert[j],"p55 duplicate expert");}
    p55_routes.write(reinterpret_cast<const char*>(prefix),sizeof(prefix));
    p55_routes.write(reinterpret_cast<const char*>(fields),sizeof(fields));
    p55_routes.write(reinterpret_cast<const char*>(expert),sizeof(expert));
    p55_routes.write(reinterpret_cast<const char*>(weight),sizeof(weight));
    p55_routes.flush();require(bool(p55_routes),"p55 route log write");
  }
  void p55_target_route(const flash::Launch& l) {
    if(l.op!="route")return;
    p55_route(l.card,integer(l.card,"position"),std::stoi(l.label.substr(4)),false,
              buffers[l.card].at(l.outputs[0]).id,buffers[l.card].at(l.outputs[1]).id,p.g.top);
  }
