// Pure CPU policy fixture: no runtime, model, SYCL or allocation dependency.
// Compile/run is deliberately pending root admission.
#include <algorithm>
#include <array>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include "../selection.hpp"
static void require(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
namespace flash {
inline unsigned grid_type(unsigned g){return g;}
struct Launch {std::string label,op;std::vector<std::string>weights,inputs,outputs;std::vector<int>shape;};
struct Plan {std::vector<Launch>launches;};
}
struct Tensor {unsigned grid=18;std::vector<int>shape{512,640,2560};size_t bytes=321126400;};
struct Weights {std::map<std::string,Tensor>directory;};
struct Options {bool expert_iq3xxs_block=true,gsq_packed=true,attention_q8_p33=true,qkv_q6_p33=true,mini=false;};
#include "build/source/policy.hpp"
static unsigned checks=0;
static void check(bool b){require(b,"fixture assertion");++checks;}
template<class F>static void refuses(F f){bool bad=false;try{f();}catch(const std::runtime_error&){bad=true;}check(bad);}
int main(){
 Weights w;Options a;flash::Plan p;
 for(auto[label,weight]:iq3_block_sites){std::string name(label),prefix=name.substr(0,name.rfind('.'));w.directory[weight]=Tensor{};p.launches.push_back({name,"routed_gemv",{weight},{prefix+".expert_input",prefix+".routes","active","error"},{name,name+".status"},{10,640,2560}});}
 iq3_block_admit(w,a,p);check(p.launches.size()==34);
 for(size_t i=0;i<p.launches.size();++i){
  const auto&good=p.launches[i];check(iq3_block_site(w,a,good));
  auto bad=good;bad.weights=p.launches[(i+1)%p.launches.size()].weights;refuses([&]{iq3_block_site(w,a,bad);});
  bad=good;bad.shape[0]=9;refuses([&]{iq3_block_site(w,a,bad);});
  bad=good;bad.op="gemv";refuses([&]{iq3_block_site(w,a,bad);});
  bad=good;bad.inputs[0]="shared-input";refuses([&]{iq3_block_site(w,a,bad);});
  bad=good;bad.outputs[1]="wrong.status";refuses([&]{iq3_block_site(w,a,bad);});
  auto wrong=w;wrong.directory.at(good.weights[0]).grid=19;refuses([&]{iq3_block_site(wrong,a,good);});
  wrong=w;wrong.directory.at(good.weights[0]).shape[0]=511;refuses([&]{iq3_block_site(wrong,a,good);});
  wrong=w;--wrong.directory.at(good.weights[0]).bytes;refuses([&]{iq3_block_site(wrong,a,good);});
 }
 auto bad=p;bad.launches.pop_back();refuses([&]{iq3_block_admit(w,a,bad);});
 bad=p;bad.launches.push_back(p.launches[0]);refuses([&]{iq3_block_admit(w,a,bad);});
 auto off=a;off.expert_iq3xxs_block=false;for(const auto&l:p.launches)check(!iq3_block_site(w,off,l));iq3_block_admit(w,off,{});++checks;
 auto invalid=a;invalid.qkv_q6_p33=false;refuses([&]{iq3_block_admit(w,invalid,p);});
 invalid=a;invalid.mini=true;refuses([&]{iq3_block_admit(w,invalid,p);});
 auto unrelated=p.launches[0];unrelated.label="blk.1.expsgate";unrelated.weights={"blk.1.ffn_gate_exps.weight"};check(!iq3_block_site(w,a,unrelated));
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"device_executed\":false}\n";
}
