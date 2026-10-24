#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
static void require(bool x,const char*m){if(!x)throw std::runtime_error(m);}
namespace iq3{enum class Type{Q6_K,Q8_0,Q5_K};}
namespace flash{
static iq3::Type grid_type(iq3::Type x){return x;}
struct Launch{std::string label,op;std::vector<std::string>weights;std::vector<int>shape;};
struct Plan{std::vector<Launch>launches;};
}
struct Tensor{iq3::Type grid;std::vector<int>shape;uint64_t bytes;};
struct Weights{std::map<std::string,Tensor>directory;};
struct Options{bool attention_q8_p33=true,gsq_packed=true,mini=false,qkv_q6_p33=true;};
#include "policy.hpp"
static unsigned checks=0;
static void check(bool x){require(x,"policy check");++checks;}
template<class F>void rejects(F f){bool threw=false;try{f();}catch(const std::exception&){threw=true;}check(threw);}
int main(){
 Weights w;Options a;flash::Plan p;
 for(auto [label,weight]:attention_q8_sites){w.directory.emplace(weight,Tensor{iq3::Type::Q8_0,{2560,6144},16711680});p.launches.push_back({label,"gemv",{weight},{1,2560,6144}});}
 for(auto [label,weight]:qkv_q6_sites){w.directory.emplace(weight,Tensor{iq3::Type::Q6_K,{10240,2560},21504000});p.launches.push_back({label,"gemv",{weight},{1,10240,2560}});}
 combined_admit(w,a,p);check(p.launches.size()==70);
 for(auto &l:p.launches){check(combined_site(w,a,l));check(combined_weight(w,a,l.weights[0]));}
 auto q=p.launches.back();
 auto swapped=q;swapped.weights=p.launches[48].weights;rejects([&]{combined_site(w,a,swapped);});
 for(int field=0;field<7;++field){auto bad=q;if(field==0)bad.label+="wrong";if(field==1)bad.op="lookup";if(field==2)bad.weights[0]+="wrong";if(field==3)bad.weights.push_back(bad.weights[0]);if(field==4)bad.shape[0]=2;if(field==5)bad.shape[1]=6144;if(field==6)bad.shape[2]=6144;rejects([&]{combined_site(w,a,bad);});}
 auto missing=p;missing.launches.pop_back();rejects([&]{combined_admit(w,a,missing);});
 auto duplicate=p;duplicate.launches.push_back(q);rejects([&]{combined_admit(w,a,duplicate);});
 for(int field=0;field<3;++field){auto bad=w;auto&t=bad.directory.at(q.weights[0]);if(field==0)t.grid=iq3::Type::Q5_K;if(field==1)t.shape[1]=6144;if(field==2)--t.bytes;rejects([&]{combined_site(bad,a,q);});}
 for(int field=0;field<3;++field){auto bad=a;if(field==0)bad.attention_q8_p33=false;if(field==1)bad.gsq_packed=false;if(field==2)bad.mini=true;rejects([&]{qkv_q6_site(w,bad,q);});}
 Options attention_only=a;attention_only.qkv_q6_p33=false;combined_admit(w,attention_only,p);check(!qkv_q6_site(w,attention_only,q));check(attention_q8_site(w,attention_only,p.launches[0]));
 for(auto label:{"blk.1.gdn.qkv","blk.0.gdn.z","output"}){flash::Launch other{label,"gemv",{"unselected.weight"},{1,10240,2560}};check(!combined_site(w,a,other));}
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"attention_sites\":48,\"qkv_sites\":22,\"scope\":\"Actual generated policy with synthetic metadata; no Engine or Device\"}\n";
}
