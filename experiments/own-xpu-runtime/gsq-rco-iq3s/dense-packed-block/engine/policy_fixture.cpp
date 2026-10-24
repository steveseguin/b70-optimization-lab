#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
static void require(bool v,const char*m){if(!v)throw std::runtime_error(m);}
namespace flash {static unsigned grid_type(unsigned t){return t;}struct Launch{std::string label,op;std::vector<std::string>weights;std::vector<int>shape;std::vector<std::string>inputs,outputs;};struct Plan{std::vector<Launch>launches;};}
struct Tensor{unsigned grid;std::vector<int>shape;uint64_t bytes;};struct Weights{std::map<std::string,Tensor>directory;};
struct Options{bool dense_packed_block=true,dense_q6_p33=true,gsq_packed=true,attention_q8_p33=true,qkv_q6_p33=true,expert_iq3xxs_block=true,mini=false;};
#include "build/source/policy.hpp"
static unsigned checks=0;static void check(bool v){require(v,"check");++checks;}
template<class F>void rejects(F f){bool thrown=false;try{f();}catch(const std::exception&){thrown=true;}check(thrown);}
int main(){Weights w;Options a;flash::Plan p;std::map<unsigned,unsigned>types;
 for(auto s:denseblock::sites){auto input=std::find_if(dense_block_inputs.begin(),dense_block_inputs.end(),[&](auto v){return s.label==v.first;});check(input!=dense_block_inputs.end());w.directory.emplace(std::string(s.weight),Tensor{s.type,{int(s.rows),2560},s.bytes});p.launches.push_back({std::string(s.label),"gemv",{std::string(s.weight)},{1,int(s.rows),2560},{input->second,"active","error"},{std::string(s.label)}});++types[s.type];}
 dense_block_admit(w,a,p);check(types==std::map<unsigned,unsigned>{{12,43},{13,31},{23,42}});
 for(const auto&l:p.launches){check(dense_block_site(w,a,l));for(int f=0;f<9;++f){auto b=l;if(f==0)b.label+="wrong";if(f==1)b.weights[0]+="wrong";if(f==2)b.op="routed_gemv";if(f==3)b.weights.push_back(b.weights[0]);if(f==4)b.shape[0]=2;if(f==5)++b.shape[1];if(f==6)b.shape[2]=512;if(f==7)b.inputs[0]+="wrong";if(f==8)b.outputs[0]+="wrong";rejects([&]{dense_block_site(w,a,b);});}for(int f=0;f<3;++f){auto b=w;auto&t=b.directory.at(l.weights[0]);if(f==0)t.grid=18;if(f==1)++t.shape[0];if(f==2)--t.bytes;rejects([&]{dense_block_site(b,a,l);});}}
 auto swapped=p.launches[0];swapped.weights=p.launches[1].weights;rejects([&]{dense_block_site(w,a,swapped);});auto missing=p;missing.launches.pop_back();rejects([&]{dense_block_admit(w,a,missing);});auto duplicate=p;duplicate.launches.push_back(p.launches[0]);rejects([&]{dense_block_admit(w,a,duplicate);});
 for(int f=0;f<6;++f){auto b=a;if(f==0)b.gsq_packed=false;if(f==1)b.attention_q8_p33=false;if(f==2)b.qkv_q6_p33=false;if(f==3)b.expert_iq3xxs_block=false;if(f==4)b.dense_q6_p33=false;if(f==5)b.mini=true;rejects([&]{dense_block_admit(w,b,p);});}
 auto off=a;off.dense_packed_block=false;dense_block_admit(w,off,p);for(const auto&l:p.launches)check(!dense_block_site(w,off,l));for(const auto&label:{"blk.0.expsgate","blk.0.attention","output"}){flash::Launch other{label,"gemv",{"other.weight"},{1,6144,2560},{"x","active","error"},{label}};check(!dense_block_site(w,a,other));}
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"sites\":116,\"allocation_delta_bytes\":0,\"scope\":\"Actual generated policy and frozen kernel selector over synthetic metadata; no Device/arithmetic execution\"}\n";
}
