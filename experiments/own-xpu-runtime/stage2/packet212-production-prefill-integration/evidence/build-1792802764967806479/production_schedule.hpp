#pragma once
// The same pure selector is consumed by the actual Engine helper and CPU census fixture.
#include <cstddef>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
namespace p212 {
inline void need(bool value,const char* reason){if(!value)throw std::invalid_argument(reason);}
struct Site {size_t index=0;std::string label,op;std::vector<std::string> weights;};
struct Tensor {std::string type;size_t rows=0,columns=0;unsigned variant=0;size_t stored_bytes=0;};
struct Layer {unsigned id=0;std::vector<size_t> sites,prefix,suffix;size_t qkv=0,z=0;bool gdn=false,paired=false;};
struct Schedule {std::vector<size_t> prefix,final;std::vector<Layer> layers;size_t pair_sites=0,skipped_originals=0;};
inline Schedule build_schedule(const std::vector<Site>& sites,const std::map<std::string,Tensor>& tensors){
 Schedule result;bool reached_layers=false,reached_final=false;std::map<std::string,size_t> unique;
 for(size_t i=0;i<sites.size();++i){const auto&s=sites[i];need(s.index==i&&unique.emplace(s.label,i).second,"p212 exact unique site identity");
  if(!s.label.starts_with("blk.")){if(!reached_layers)result.prefix.push_back(i);else{reached_final=true;result.final.push_back(i);}continue;}
  need(!reached_final,"p212 interleaved final/block schedule");reached_layers=true;
  auto dot=s.label.find('.',4);need(dot!=std::string::npos&&dot>4,"p212 layer label");unsigned id=0;
  for(size_t j=4;j<dot;++j){need(s.label[j]>='0'&&s.label[j]<='9',"p212 numeric layer");id=id*10+unsigned(s.label[j]-'0');need(id<48,"p212 layer range");}
  if(result.layers.empty()||result.layers.back().id!=id){need(id==result.layers.size(),"p212 complete ordered48layers");Layer layer;layer.id=id;result.layers.push_back(layer);}
  result.layers.back().sites.push_back(i);
 }
 need(result.layers.size()==48&&!result.prefix.empty()&&!result.final.empty(),"p212 production plan coverage");
 unsigned gdn=0,qsa=0,fallback=0;
 for(auto& layer:result.layers){auto tag="blk."+std::to_string(layer.id)+".";auto q=unique.find(tag+"gdn.qkv"),z=unique.find(tag+"gdn.z");
  layer.gdn=q!=unique.end();need(layer.gdn==(z!=unique.end()),"p212 incomplete GDN projection tuple");
  if(!layer.gdn){++qsa;need(unique.count(tag+"qsa.attention")||unique.count(tag+"qsa.attn"),"p212 missing QSA attention");layer.suffix=layer.sites;continue;}
  ++gdn;layer.qkv=q->second;layer.z=z->second;need(layer.z==layer.qkv+1&&layer.qkv>0&&sites[layer.qkv-1].label==tag+"hc.a.inject","p212 selected projection order");
  const auto& a=sites[layer.qkv];const auto&b=sites[layer.z];need(a.op=="gemv"&&b.op=="gemv"&&a.weights.size()==1&&b.weights.size()==1,"p212 projection launch ABI");
  const auto&x=tensors.at(a.weights[0]);const auto&y=tensors.at(b.weights[0]);
  need(x.columns==2560&&y.columns==2560&&x.rows==10240&&y.rows==6144&&x.type==y.type&&x.variant==6&&y.variant==6,"p212 projection type/layout tuple");
  if(x.type=="Q6_K"){need(layer.id!=2&&x.stored_bytes==x.rows*3380&&y.stored_bytes==y.rows*3380,"p212 exact Q6 resident stride");layer.paired=true;result.pair_sites+=2;result.skipped_originals+=4;}
  else {need(layer.id==2&&x.type=="Q8_0"&&x.stored_bytes==31129600&&y.stored_bytes==18677760,"p212 exact Q8 original fallback");++fallback;}
  for(auto index:layer.sites){if(layer.paired&&index<layer.qkv)layer.prefix.push_back(index);else if(!layer.paired||(index!=layer.qkv&&index!=layer.z))layer.suffix.push_back(index);}
 }
 need(gdn==36&&qsa==12&&fallback==1&&result.pair_sites==70&&result.skipped_originals==140,"p212 selected production projection inventory");return result;
}
enum class StepKind { site, pair };
struct Step {StepKind kind;size_t index;unsigned row;};
inline std::vector<Step> ordered_steps(const Schedule& schedule){std::vector<Step> out;auto row_sites=[&](const std::vector<size_t>&sites,unsigned row){for(auto index:sites)out.push_back({StepKind::site,index,row});};for(unsigned row=0;row<2;++row)row_sites(schedule.prefix,row);for(const auto&layer:schedule.layers){if(layer.paired){for(unsigned row=0;row<2;++row)row_sites(layer.prefix,row);out.push_back({StepKind::pair,layer.qkv,2});out.push_back({StepKind::pair,layer.z,2});}for(unsigned row=0;row<2;++row)row_sites(layer.suffix,row);}return out;}
inline size_t route_offset(unsigned row,unsigned layer){need(row<2&&layer<48,"p212 row/layer route slot");return (size_t(row)*48+layer)*10;}
inline std::vector<uint32_t> chronological_routes(const std::vector<uint32_t>& experts){need(experts.size()==960,"p212 complete2x48x10routes");std::vector<uint32_t> result;result.reserve(960);for(unsigned row=0;row<2;++row)for(unsigned layer=0;layer<48;++layer)for(unsigned k=0;k<10;++k){auto id=experts[route_offset(row,layer)+k];need(id<512,"p212 routed expert bounds");result.push_back(layer*512+id);}return result;}
inline void admit_chunk(size_t start,size_t input_count,size_t context){need(context==4096&&start<context&&input_count<=context&&start+2<input_count&&start/32==(start+1)/32,"p212 two nonfinal positions/capacity");}
} // namespace p212
