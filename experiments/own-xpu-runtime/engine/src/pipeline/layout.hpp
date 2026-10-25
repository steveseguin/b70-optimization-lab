#pragma once
#include "stage2/packet3/kernels/api.hpp"
#include <algorithm>
#include <set>
#include <string>
#include <vector>

namespace ownrt::pipeline_layout {
inline void require(bool value,const char* message){if(!value)throw std::invalid_argument(message);}
inline void validate_fusion(const char* value){require(!value||std::string(value)!="1","pipeline refuses OWNRT_GSQ_FUSE_NORM=1 cross-layer fusion");}
inline std::vector<int> parse(const std::string& text){
 require(!text.empty()&&text.back()!=',',"pipeline boundaries must be comma-separated integers");
 std::vector<int> result;size_t start=0;
 while(start<text.size()){
  const auto end=text.find(',',start);const auto token=text.substr(start,end==std::string::npos?end:end-start);
  require(!token.empty()&&std::all_of(token.begin(),token.end(),[](char c){return c>='0'&&c<='9';}),"invalid pipeline boundary");
  size_t consumed=0;int value=std::stoi(token,&consumed);require(consumed==token.size(),"invalid pipeline boundary");
  result.push_back(value);if(end==std::string::npos)break;start=end+1;
 }
 require(result.size()>=2&&result.front()==0,"pipeline boundaries must begin at zero and contain an end");
 for(size_t i=1;i<result.size();++i)require(result[i]>result[i-1],"pipeline stages must be nonempty and ordered");
 return result;
}
inline int layer(const std::string& label){
 if(!label.starts_with("blk."))return -1;
 const auto end=label.find('.',4);require(end!=std::string::npos,"pipeline layer label");
 const auto number=label.substr(4,end-4);require(!number.empty()&&std::all_of(number.begin(),number.end(),[](char c){return c>='0'&&c<='9';}),"pipeline layer number");
 return std::stoi(number);
}
inline flash::Plan slice(flash::Plan p,const std::vector<int>& boundaries,int stage){
 require(boundaries.size()>=2&&boundaries.front()==0&&stage>=0&&size_t(stage+1)<boundaries.size(),"pipeline stage identity");
 for(size_t i=1;i<boundaries.size();++i)require(boundaries[i]>boundaries[i-1],"pipeline stage extent");
 std::set<int> layers;for(const auto& launch:p.launches){int n=layer(launch.label);if(n>=0)layers.insert(n);}
 require(!layers.empty()&&*layers.begin()==0&&int(layers.size())==*layers.rbegin()+1&&boundaries.back()==int(layers.size()),"pipeline boundaries must cover every model layer");
 const bool first=stage==0,last=size_t(stage+2)==boundaries.size();
 std::vector<flash::Launch> launches;
 for(auto launch:p.launches){
  require(launch.op!="handoff"&&launch.op!="handoff_result","pipeline slicing requires flattened local plan");
  const int number=layer(launch.label);bool keep=false;
  if(number>=0)keep=number>=boundaries[stage]&&number<boundaries[stage+1];
  else if(launch.op=="begin"||launch.op=="commit")keep=true;
  else if(launch.label=="embedding"||launch.label=="streams")keep=first;
  else if(launch.label.starts_with("final.")||launch.label=="logits"||launch.label=="argmax")keep=last;
  else throw std::invalid_argument("unclassified pipeline global launch: "+launch.label);
  if(keep){
   for(const auto* names:{&launch.inputs,&launch.outputs,&launch.weights})for(const auto& name:*names){const int owner=layer(name);require(owner<0||(owner>=boundaries[stage]&&owner<boundaries[stage+1]),"pipeline launch has cross-stage tensor dependency");}
   // Current host lookup/history preparation belongs to the first stage.
   require(first||launch.op!="lookup","pipeline boundary moves host lookup outside first stage");
   launch.card=0;launch.source_card=-1;launches.push_back(std::move(launch));
  }
 }
 p.launches=std::move(launches);
 std::set<std::string> used{"streams","token","position","active","error","next_token"};
 for(const auto& launch:p.launches){used.insert(launch.inputs.begin(),launch.inputs.end());used.insert(launch.outputs.begin(),launch.outputs.end());}
 std::erase_if(p.buffers,[&](const auto& buffer){return !used.count(buffer.name);});
 for(auto& buffer:p.buffers)buffer.card=0;
 return p;
}
} // namespace ownrt::pipeline_layout
