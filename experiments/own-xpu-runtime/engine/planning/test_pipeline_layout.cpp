// Metadata-only test: opens placement TSV, never model weights or a GPU device.
#include "pipeline/layout.hpp"
#include "stage2/packet3/step/plan.hpp"
#include <cassert>
#include <iostream>
#include <tuple>
using namespace ownrt::pipeline_layout;
static flash::Plan legacy(flash::Plan p,int rank,int boundary){
 std::erase_if(p.launches,[&](const auto& l){if(layer(l.label)>=0)return rank==0?layer(l.label)>=boundary:layer(l.label)<boundary;
  if(l.op=="begin"||l.op=="commit")return false;return (l.label=="embedding"||l.label=="streams")?rank!=0:rank!=1;});
 std::set<std::string> used{"streams","token","position","active","error","next_token"};
 for(auto& l:p.launches){used.insert(l.inputs.begin(),l.inputs.end());used.insert(l.outputs.begin(),l.outputs.end());l.card=0;l.source_card=-1;}
 std::erase_if(p.buffers,[&](auto& b){return !used.count(b.name);});for(auto& b:p.buffers)b.card=0;return p;
}
static auto launch_fields(const flash::Launch& l){return std::tie(l.op,l.label,l.inputs,l.outputs,l.weights,l.shape,l.card,l.parameter,l.source_card,l.weight_bytes,l.read_bytes,l.write_bytes,l.row_begin,l.row_count);}
static auto buffer_fields(const flash::Buffer& b){return std::tie(b.name,b.shape,b.type,b.card);}
static void equivalent(const flash::Plan& a,const flash::Plan& b){assert(a.launches.size()==b.launches.size()&&a.buffers.size()==b.buffers.size());for(size_t i=0;i<a.launches.size();++i)assert(launch_fields(a.launches[i])==launch_fields(b.launches[i]));for(size_t i=0;i<a.buffers.size();++i)assert(buffer_fields(a.buffers[i])==buffer_fields(b.buffers[i]));}
template<class F> static void rejects(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
int main(int argc,char** argv){
 assert(argc==2);std::ifstream input(argv[1]);assert(input);flash::Directory directory;std::string line;
 while(std::getline(input,line)){std::istringstream row(line);std::string shard,name,component;int kind,layer,mask,ndim;uint64_t offset,bytes;row>>shard>>name>>component>>kind>>offset>>bytes>>layer>>mask>>ndim;assert(row&&ndim>0);std::vector<int> shape(ndim);for(auto& n:shape)row>>n;assert(row);std::reverse(shape.begin(),shape.end());assert(directory.emplace(name,flash::Tensor{name,flash::grid_name(flash::Type(kind)),component,shape,bytes}).second);}
 auto g=flash::geometry_from_directory(directory);g.context=16;std::vector<bool> attention;for(int i=0;i<48;++i)attention.push_back(directory.count("blk."+std::to_string(i)+".attn_q.weight"));
 auto full=flash::Builder(g,&directory).activation(flash::Scalar::f32).build(attention);
 for(auto& b:full.buffers)b.card=0;for(auto& l:full.launches){l.card=0;l.source_card=-1;}
 std::erase_if(full.launches,[](const auto& l){return l.op=="handoff"||l.op=="handoff_result"||l.label=="begin.1"||l.label=="commit.0";});
 for(int rank=0;rank<2;++rank)equivalent(slice(full,{0,23,48},rank),legacy(full,rank,23));
 std::set<std::string> full_weights;for(const auto& l:full.launches)full_weights.insert(l.weights.begin(),l.weights.end());
 for(const auto& cuts:std::vector<std::vector<int>>{{0,48},{0,23,48},{0,13,25,37,48},{0,8,16,24,32,40,48}}){
  std::map<std::string,int> owner;std::set<std::string> layer_launches;std::set<int> covered;
  for(size_t stage=0;stage+1<cuts.size();++stage){auto part=slice(full,cuts,int(stage));uint64_t packed=0;
   for(const auto& l:part.launches){int n=layer(l.label);if(n>=0){assert(n>=cuts[stage]&&n<cuts[stage+1]);covered.insert(n);assert(layer_launches.insert(l.label).second);}
    if(l.label=="embedding"||l.op=="lookup")assert(stage==0);if(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax")assert(stage+2==cuts.size());
    for(const auto& name:l.weights){auto [it,added]=owner.emplace(name,int(stage));assert(it->second==int(stage));if(added&&directory.at(name).component!="embedding"&&directory.at(name).component!="ple_lookup")packed+=directory.at(name).bytes;}
   }
   std::cout<<"stages="<<cuts.size()-1<<" stage="<<stage<<" layers="<<cuts[stage]<<":"<<cuts[stage+1]<<" packed_device_weights="<<packed<<"\n";
  }
  assert(covered.size()==48&&owner.size()==full_weights.size());for(auto& name:full_weights)assert(owner.count(name));
  for(auto& l:full.launches)if(layer(l.label)>=0)assert(layer_launches.count(l.label));
 }
 for(auto bad:{"","0,","1,48","0,0,48","0,-1,48","0,49,48","0,1x,48"})rejects([&]{parse(bad);});
 rejects([&]{slice(full,{0,47},0);});rejects([&]{slice(full,{0,23,48},2);});rejects([&]{slice(full,{0,1,48},1);});
 validate_fusion(nullptr);validate_fusion("0");rejects([&]{validate_fusion("1");});
 auto cross=full;for(auto& l:cross.launches)if(layer(l.label)==12){l.outputs.push_back("blk.13.cross_cut");break;}rejects([&]{slice(cross,{0,13,25,37,48},0);});
 auto unknown=full;unknown.launches.push_back({"test","unregistered-global"});rejects([&]{slice(unknown,{0,48},0);});
 std::cout<<"PASS: exact legacy split equivalence, 1/2/4/6 stage layer+weight ownership, invalid boundary rejection\n";
}
