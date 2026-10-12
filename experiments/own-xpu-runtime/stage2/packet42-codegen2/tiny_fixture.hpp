#pragma once
#include "tiny_core.hpp"
#include <filesystem>
#include <fstream>
#include <cstring>
namespace p42tiny {
struct Fixture{
 ng::Shape s;std::array<std::vector<uint8_t>,19> data;std::array<bool,19> outputs{};std::string name;bool alias_history=false;
 const std::vector<uint8_t>&output_bytes(int j)const{return data[alias_history&&j==4?1:j];}
 std::vector<uint8_t>&output_bytes(int j){return data[alias_history&&j==4?1:j];}
 ng::Args args(){ng::Args a;for(int j=0;j<19;++j)a.p[j]=data[j].data();if(alias_history)a.p[4]=a.p[1];return a;}
 static std::vector<uint8_t>integer(int v){std::vector<uint8_t>b(4);std::memcpy(b.data(),&v,4);return b;}
 explicit Fixture(const std::filesystem::path&p):name(p.filename().string()){
  std::ifstream f(p,std::ios::binary);f.read(reinterpret_cast<char*>(&s),sizeof s);ng::validate(s);
  for(int j=0;j<16;++j){uint32_t n=0,out=0;f.read(reinterpret_cast<char*>(&n),4);f.read(reinterpret_cast<char*>(&out),4);if(!n||n>128*1024*1024)throw std::runtime_error("fixture length");data[j].resize(n);outputs[j]=out;f.read(reinterpret_cast<char*>(data[j].data()),n);if(out)f.seekg(n,std::ios::cur);}
  if(!f||f.peek()!=EOF)throw std::runtime_error("fixture truncated");int ctrl[3];std::memcpy(ctrl,data[15].data(),12);data[15]=integer(ctrl[2]);data[17]=integer(ctrl[0]);data[18]=integer(ctrl[1]);std::ifstream rope(std::filesystem::path(__FILE__).parent_path()/"../packet29-merged/rope.bf16",std::ios::binary);data[16].assign(std::istreambuf_iterator<char>(rope),{});if(data[16].size()!=rope_constants::bytes)throw std::runtime_error("rope fixture bytes");outputs[15]=true;
 }
 explicit Fixture(ng::Shape shape,std::string label):s(shape),name(label){auto sizes=ng::required_bytes(s);for(int j=0;j<19;++j){data[j].resize(std::max(size_t(4),sizes[j]));for(size_t k=0;k<data[j].size()/2;++k){uint16_t v=ng::Args::bits(float(int((k*17+j*11)%71)-35)*.03125f);std::memcpy(data[j].data()+2*k,&v,2);}}data[15]=integer(0);data[17]=integer(0);data[18]=integer(1);outputs[15]=true;outputs[s.op==ng::conv?3:s.op==ng::moe_combine?4:2]=true;if(s.op==ng::conv)outputs[4]=true;if(s.op==ng::moe_combine)for(int j=0;j<s.extra*s.tokens;++j){float v=1.f/s.extra;std::memcpy(data[1].data()+4*j,&v,4);}}
 bool equal(const Fixture&f)const{for(int j=0;j<19;++j)if(outputs[j]&&output_bytes(j)!=f.output_bytes(j))return false;return true;}
};
inline bool supported(int op){return op==ng::conv||op==ng::activation||op==ng::mix||op==ng::moe_combine||op==ng::gated_norm||op==ng::prepare||op==ng::pool;}
inline std::vector<Fixture>fixtures(){std::vector<Fixture> v;auto dir=std::filesystem::path(__FILE__).parent_path()/"../packet29-merged/build/fusion-fixtures";for(auto&p:std::filesystem::directory_iterator(dir))if(p.path().extension()==".fixture"){std::ifstream f(p.path(),std::ios::binary);ng::Shape s;f.read(reinterpret_cast<char*>(&s),sizeof s);if(supported(s.op))v.emplace_back(p.path());}// Production-shape variants derive from inherited input bytes. Float gains
 // are exact BF16-to-FP32 conversions; no source checkpoint is involved.
 for(const auto& base:std::vector<Fixture>(v)){
  if(base.name!="qsa-prepare-1.fixture"&&base.name!="qsa-pool-1.fixture"&&base.name!="gdn-gated-1.fixture"&&base.name!="conv-10240-1.fixture")continue;
  Fixture f=base;f.s.capacity=256;f.s.flags=8;f.name="production-"+base.name;
  std::vector<int>weights=f.s.op==ng::prepare?std::vector<int>{3,4,5}:f.s.op==ng::pool?std::vector<int>{3}:std::vector<int>{2};
  for(int slot:weights){auto values=f.data[slot];f.data[slot].resize(values.size()*2);for(size_t j=0;j<values.size()/2;++j){uint16_t bits;std::memcpy(&bits,values.data()+2*j,2);float value=std::bit_cast<float>(uint32_t(bits)<<16);std::memcpy(f.data[slot].data()+4*j,&value,4);}}
  auto sizes=ng::required_bytes(f.s);for(int j=0;j<19;++j)f.data[j].resize(std::max(f.data[j].size(),sizes[j]),0);
  if(f.s.op==ng::pool){f.data[17]=Fixture::integer(3);v.push_back(f);f.name="production-pool-position255.fixture";
   // Retained pools must describe the retained raw history. Seed the 63
   // completed pools through the incumbent schedule, then independently check
   // Core recomputation and candidate bytes at the final position in CPU gates.
   for(int pos=3;pos<255;pos+=4){f.data[17]=Fixture::integer(pos);ng::cpu(f.s,f.args());}
   f.data[17]=Fixture::integer(255);v.push_back(f);}else v.push_back(f);
 }
 for(auto f:std::vector<Fixture>(v))if(f.s.op==ng::conv){f.alias_history=true;f.name+=".inplace";v.push_back(f);}
 std::sort(v.begin(),v.end(),[](auto&a,auto&b){return a.name<b.name;});return v;}
}
