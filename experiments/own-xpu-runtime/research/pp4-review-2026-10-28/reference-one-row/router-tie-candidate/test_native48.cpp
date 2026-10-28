#include "stage2/packet194-expert-diet-engine/router_tie_diagnostic.hpp"
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <filesystem>
#include <fstream>
#include <cassert>
#include <iostream>
using namespace routertie;
template<class A>A load(std::filesystem::path p){A a{};std::ifstream f(p,std::ios::binary);f.read((char*)a.data(),sizeof(a));assert(f.gcount()==sizeof(a)&&f.peek()==EOF);return a;}
int main(int argc,char**argv){assert(argc==2);std::filesystem::path base=argv[1];int changes=0,layers_changed=0;
for(int layer=0;layer<48;++layer){auto path=[&](const char*s){return base/("blk."+std::to_string(layer)+"."+s+".bin");};auto x=load<Scores>(path("router"));auto actual=load<IDs>(path("ids"));auto w=load<Weights>(path("prob"));auto r=load<Routes>(path("routes")),d=load<Routes>(path("routes.down"));
std::vector<float>input(2560),expert(25600),weights(10),scratch;IDs host{};Routes hr{},hd{};int32_t error=0,pos=177,active=1;ng::Shape shape;shape.op=ng::route_gather;shape.width=512;shape.extra=10;shape.heads=4;shape.flags=ng::f32_activations_flag;shape.capacity=4096;ng::Args args;args.f32=true;args.p[0]=x.data();args.p[1]=input.data();args.p[2]=host.data();args.p[3]=weights.data();args.p[4]=expert.data();args.p[5]=hr.data();args.p[6]=hd.data();args.p[15]=&error;args.p[17]=&pos;args.p[18]=&active;scratch.resize(specialised::scratch_floats(shape));
auto run=[&]<int ST>(){for(size_t i=0;i<specialised::work_items(shape,ST);++i)specialised::body<ng::route_gather,ST>(shape,args,i,scratch.data(),specialised::HostGuard{});};run.template operator()<0>();run.template operator()<1>();run.template operator()<2>();run.template operator()<3>();run.template operator()<4>();assert(!error);Scores probabilities;std::copy_n(scratch.data()+2*((512+31)/32)+512,512,probabilities.begin());
try{auto result=prepare(x,probabilities,host,actual,w,r,d);changes+=result.changed;layers_changed+=result.changed>0;}catch(const std::exception&e){std::cerr<<"layer "<<layer<<": "<<e.what()<<"\n";return 1;}
}
std::cout<<"PASS 48 actual sealed native vectors; changed_layers="<<layers_changed<<" changed_slots="<<changes<<"\n";
}
