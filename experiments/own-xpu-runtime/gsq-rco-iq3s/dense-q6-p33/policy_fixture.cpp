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
namespace iq3{enum class Type{Q6_K,Q5_K,BF16};}
namespace flash{static iq3::Type grid_type(iq3::Type t){return t;}struct Launch{std::string label,op;std::vector<std::string>weights;std::vector<int>shape;};struct Plan{std::vector<Launch>launches;};}
struct Tensor{iq3::Type grid;std::vector<int>shape;uint64_t bytes;};
struct Weights{std::map<std::string,Tensor>directory;};
struct Options{bool dense_q6_p33=true,gsq_packed=true,attention_q8_p33=true,qkv_q6_p33=true,expert_iq3xxs_block=true,mini=false;};
struct Matrix{iq3::Type type=iq3::Type::Q6_K,activation=iq3::Type::BF16,output_type=iq3::Type::BF16;unsigned rows=6144,columns=2560,fp32=0,routes=0,status=0,count=1,experts=1,span=6144;};
#include "build/source/policy.hpp"
static unsigned checks=0;
void check(bool v){require(v,"check");++checks;}
template<class F>void rejects(F f){bool thrown=false;try{f();}catch(const std::exception&){thrown=true;}check(thrown);}
int main(){
 Weights w;Options a;flash::Plan p;uint64_t delta=0;unsigned z=0,q=0;
 for(auto s:dense_q6_sites){w.directory.emplace(s.weight,Tensor{iq3::Type::Q6_K,{int(s.rows),2560},uint64_t(s.rows)*2100});p.launches.push_back({s.label,"gemv",{s.weight},{1,int(s.rows),2560}});delta+=uint64_t(s.rows)*1280;if(s.rows==6144)++z;else ++q;}
 dense_q6_admit(w,a,p);check(p.launches.size()==19&&z==14&&q==5&&delta==188743680);
 for(auto&l:p.launches){check(dense_q6_site(w,a,l));check(dense_q6_weight(w,a,l.weights[0]));
  for(int field=0;field<7;++field){auto b=l;if(field==0)b.label+="wrong";if(field==1)b.weights[0]+="wrong";if(field==2)b.op="routed_gemv";if(field==3)b.weights.push_back(b.weights[0]);if(field==4)b.shape[0]=2;if(field==5)++b.shape[1];if(field==6)b.shape[2]=6144;rejects([&]{dense_q6_site(w,a,b);});}
  for(int field=0;field<3;++field){auto b=w;auto&t=b.directory.at(l.weights[0]);if(field==0)t.grid=iq3::Type::Q5_K;if(field==1)++t.shape[0];if(field==2)--t.bytes;rejects([&]{dense_q6_site(b,a,l);});}
 }
 for(auto rows:{6144u,12288u}){Matrix m;m.rows=m.span=rows;flash::Launch l{"","gemv",{},{1,int(rows),2560}};dense_q6_matrix(m,l,6,size_t(rows)*3380);check(true);m.span=0;dense_q6_matrix(m,l,6,size_t(rows)*3380);check(true);
 for(int f=0;f<13;++f){auto b=m;auto launch=l;unsigned variant=6;size_t bytes=size_t(rows)*3380;if(f==0)b.type=iq3::Type::Q5_K;if(f==1)++b.rows;if(f==2)b.columns=6144;if(f==3)variant=7;if(f==4)b.activation=iq3::Type::Q5_K;if(f==5)b.output_type=iq3::Type::Q5_K;if(f==6)b.fp32=1;if(f==7)b.routes=1;if(f==8)b.status=1;if(f==9)b.count=2;if(f==10)b.experts=2;if(f==11)b.span=1;if(f==12)--bytes;rejects([&]{dense_q6_matrix(b,launch,variant,bytes);});}}
 auto swapped=p.launches[0];swapped.weights=p.launches[1].weights;rejects([&]{dense_q6_site(w,a,swapped);});
 auto missing=p;missing.launches.pop_back();rejects([&]{dense_q6_admit(w,a,missing);});auto duplicate=p;duplicate.launches.push_back(p.launches[0]);rejects([&]{dense_q6_admit(w,a,duplicate);});
 for(int field=0;field<5;++field){auto b=a;if(field==0)b.gsq_packed=false;if(field==1)b.attention_q8_p33=false;if(field==2)b.qkv_q6_p33=false;if(field==3)b.expert_iq3xxs_block=false;if(field==4)b.mini=true;rejects([&]{dense_q6_admit(w,b,p);});}
 auto off=a;off.dense_q6_p33=false;dense_q6_admit(w,off,p);for(auto&l:p.launches){check(!dense_q6_site(w,off,l));check(!dense_q6_weight(w,off,l.weights[0]));}
 for(auto name:{"blk.0.gdn.z","blk.7.qsa.qgate","blk.0.gdn.qkv","output"}){flash::Launch other{name,"gemv",{"other.weight"},{1,6144,2560}};check(!dense_q6_site(w,a,other));}
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"sites\":19,\"scope\":\"Actual generated selector over synthetic metadata; no Device or arithmetic execution\"}\n";
}
