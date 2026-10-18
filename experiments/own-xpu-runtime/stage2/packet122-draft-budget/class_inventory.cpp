#include "../packet3/step/plan.hpp"
#include "p59c_select.hpp"
#include <iostream>
int main(int argc,char**argv){if(argc!=2)return 1;std::ifstream input(argv[1]);std::map<std::string,std::string>selection;std::string key,value;while(input>>key>>value)selection[key]=value;
 p59c::validate(selection);flash::Geometry g;g.context=4096;auto plan=flash::Builder(g).build({true});
 for(auto label:{"merge.embedding_norm","merge.hidden_norm","merge.embedding_projected","merge.projected","merge.add"})std::cout<<"draft."<<label<<'\n';
 for(const auto&l:plan.launches){if(l.op=="lookup"||l.op=="broadcast"||l.label=="blk.0.expsup")continue;
  auto found=p59c::consumers.find(l.label);if(found!=p59c::consumers.end()&&selection.at(found->second)=="packet59")continue;
  std::cout<<"draft."<<l.label<<'\n';
 }
}
