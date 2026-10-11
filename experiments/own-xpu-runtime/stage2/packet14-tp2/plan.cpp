#include "tp.hpp"
#include <fstream>
#include <iostream>
#include <set>
int main(int argc,char** argv) {
 if(argc!=2)throw std::invalid_argument("directory TSV");
 std::ifstream file(argv[1]);auto directory=flash::read_directory(file);auto p=flash::model_plan(directory);
 std::map<std::string,flash::Launch> used;
 std::map<int,uint64_t> bytes,copies;
 for(const auto& l:p.launches) {
  for(const auto& name:l.weights)used.try_emplace(name,l);
  if(!l.label.starts_with("blk."))continue;
  int layer=std::stoi(l.label.substr(4));
  if(l.op=="gemv" && l.shape[1]>=2){bytes[layer]+=l.shape[1]*2;copies[layer]+=2;}
  if(l.op=="routed_gemv"){bytes[layer]+=p.g.top*l.shape[1]*2;copies[layer]+=2;}
  if(l.op=="conv"){bytes[layer]+=l.shape[0]*2;copies[layer]+=2;}
  if(l.op=="gdn"){bytes[layer]+=p.g.vh*p.g.d*2;copies[layer]+=2;}
  if(l.op=="qsa_attention"){bytes[layer]+=p.g.qh*p.g.ad*2;copies[layer]+=2;}
 }
 if(used.size()!=directory.size() || used.size()!=1224)throw std::runtime_error("tensor coverage");
 std::cout<<"{\"tensors\":[";bool comma=false;
 for(const auto& [name,t]:directory) {
  const auto& l=used.at(name);std::string placement="replicated-control";size_t n=1;
  if(l.op=="lookup")placement="host-lookup";
  else if(l.op=="routed_gemv"){placement="expert-id";n=p.g.experts;}
  else if(l.op=="gemv" && l.shape[1]>=2){placement="output-rows";n=l.shape[1];}
  std::cout<<(comma?",":"")<<"{\"name\":"<<ownrt::quote(name)<<",\"placement\":"<<ownrt::quote(placement)<<",\"extent\":"<<n;
  if(n>1)std::cout<<",\"A\":[0,"<<n/2<<"],\"B\":["<<n/2<<","<<n<<"]";
  std::cout<<"}";comma=true;
 }
 std::cout<<"],\"layers\":[";comma=false;
 for(auto [layer,n]:bytes){std::cout<<(comma?",":"")<<"{\"layer\":"<<layer<<",\"peer_bytes\":"<<n<<",\"max_peer_copies\":"<<copies[layer]<<"}";comma=true;}
 std::cout<<"],\"measured\":false}\n";
}
