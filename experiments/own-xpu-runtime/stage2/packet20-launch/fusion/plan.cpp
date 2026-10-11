#include "../../packet3/step/plan.hpp"
#include <iostream>
void strings(const std::vector<std::string>&xs){std::cout<<"[";for(size_t j=0;j<xs.size();++j)std::cout<<(j?",":"")<<"\""<<xs[j]<<"\"";std::cout<<"]";}
int main(){flash::Geometry g;g.context=256;std::vector<bool> full(48);for(int i=0;i<48;++i)full[i]=i%4==3;auto p=flash::Builder(g).build(full);std::vector<flash::Launch> fused;
for(size_t i=0;i<p.launches.size();++i){auto l=p.launches[i];if(l.op=="routed_gemv"&&l.weights[0].find("ffn_gate_exps")!=std::string::npos){const auto&up=p.launches[i+2];l.op="expert_gate_up";l.weights.push_back(up.weights[0]);l.outputs.insert(l.outputs.end(),up.outputs.begin(),up.outputs.end());fused.push_back(l);fused.push_back(p.launches[i+1]);i+=2;}else fused.push_back(l);}p.launches=std::move(fused);
std::cout<<"[";bool first=true;for(auto&l:p.launches){if(!first)std::cout<<",";first=false;std::cout<<"{\"label\":\""<<l.label<<"\",\"op\":\""<<l.op<<"\",\"card\":"<<l.card<<",\"inputs\":";strings(l.inputs);std::cout<<",\"outputs\":";strings(l.outputs);std::cout<<",\"weights\":";strings(l.weights);std::cout<<"}";}std::cout<<"]\n";}
