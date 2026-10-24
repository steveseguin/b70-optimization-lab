// Synthetic header-only test executable. It is not a native model launcher.
#include "gguf.hpp"
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
using namespace iq3;
Admission admission(const char* expected,const char* auth) {
  Admission a;a.expected=read_plan(expected);std::ifstream in(auth);if(!in)throw std::runtime_error("auth open");
  std::string line;
  while(std::getline(in,line)) {
    std::istringstream s(line);ShardIdentity e;std::string extra;
    if(!(s>>e.basename>>e.bytes>>e.dev>>e.ino>>e.mtime_ns>>e.ctime_ns) || (s>>extra))throw std::runtime_error("auth row");
    a.shards.push_back(e);
  }
  return a;
}
int main(int argc,char**argv) {
  try {
    if(argc!=7)throw std::runtime_error("args: mode candidate-plan trusted-plan trusted-auth shard0 shard1");
    std::vector<std::filesystem::path> paths={argv[5],argv[6]};auto plan=read_plan(argv[2]);
    std::unique_ptr<Model> model;
    if(std::string(argv[1])=="default")model=std::make_unique<Model>(paths,std::move(plan));
    else if(std::string(argv[1])=="bound")model=std::make_unique<Model>(paths,std::move(plan),admission(argv[3],argv[4]));
    else throw std::runtime_error("mode");
    auto totals=model->census();std::set<unsigned> types;uint64_t read=0;
    for(auto& t:model->plan)types.insert(unsigned(t.type));for(auto& s:model->shards){if(s.read_bytes!=s.header_bytes)throw std::runtime_error("header read accounting");read+=s.read_bytes;}
    std::cout<<"{\"passed\":true,\"tensors\":"<<model->plan.size()<<",\"types\":"<<types.size()<<",\"header_bytes_read\":"<<read<<",\"payload_bytes_read\":0,\"census\":["<<totals[0]<<","<<totals[1]<<","<<totals[2]<<"]}\n";
    return 0;
  } catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 2;}
}
