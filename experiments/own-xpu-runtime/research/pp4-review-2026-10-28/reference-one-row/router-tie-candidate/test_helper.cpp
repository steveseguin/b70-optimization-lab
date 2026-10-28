#include "stage2/packet194-expert-diet-engine/router_tie_diagnostic.hpp"
#include <cassert>
#include <fstream>
#include <filesystem>
#include <limits>
#include <iostream>
namespace fs=std::filesystem;using namespace routertie;
template<class A>A load(fs::path p){A a{};std::ifstream f(p,std::ios::binary);f.read((char*)a.data(),sizeof(a));assert(f.gcount()==sizeof(a)&&f.peek()==EOF);return a;}
int main(int argc,char**argv){assert(argc==2);fs::path base=argv[1];int cases=0;
 for(auto mode:{"native","cpu"}){
  auto dir=base/(std::string(mode)+"-replay");auto x=load<Scores>(dir/"input-logits.f32"),p=load<Scores>(dir/"native-probs.f32");auto ids=load<IDs>(dir/"native-ids.i32"),ggml=load<IDs>(dir/"ggml-ids.i32");auto w=load<Weights>(dir/"native-weights.f32");auto r=load<Routes>(dir/"native-routes.i32"),d=load<Routes>(dir/"native-routes-down.i32");auto before=w;
  auto decision=prepare(x,p,ids,ids,w,r,d);assert(decision.ids==ggml);assert(w==before);if(std::string(mode)=="native")assert(decision.changed>0);else assert(decision.changed==0);
  int writes=0;publish(decision,[&](int which,const void*ptr,size_t n){assert(ptr&&which==writes&&n==(which?120:40));++writes;});assert(writes==(decision.changed?3:0));++cases;
 }
 Scores x{},p{};IDs ids{};Weights w{};Routes r{},d{};for(int i=0;i<512;++i){x[i]=float(512-i);p[i]=float(512-i)/1000;}for(int i=0;i<10;++i){ids[i]=i;w[i]=.1f;r[3*i]=d[3*i]=i;r[3*i+2]=640;d[3*i+2]=2560;}
 assert(prepare(x,p,ids,ids,w,r,d).changed==0);++cases;
 auto refuse=[&](auto fn){bool rejected=false;int calls=0;try{auto z=fn();publish(z,[&](int,const void*,size_t){++calls;});}catch(const std::exception&){rejected=true;}assert(rejected&&calls==0);++cases;};
 refuse([&]{auto y=x;y[2]=std::numeric_limits<float>::quiet_NaN();return prepare(y,p,ids,ids,w,r,d);});
 refuse([&]{auto host=ids;host[9]=42;return prepare(x,p,host,ids,w,r,d);});
 refuse([&]{auto z=r;z[2]=639;return prepare(x,p,ids,ids,w,z,d);});
 refuse([&]{auto prob=p;prob.fill(.5f);return prepare(x,prob,ids,ids,w,r,d);}); // probability-only tie unequal raw scores
 refuse([&]{Scores y{},prob{};prob.fill(.5f);y[0]=-0.f;return prepare(y,prob,ids,ids,w,r,d);}); // signed-zero words differ
 Scores all{},prob{};prob.fill(1.f/512);auto tied=prepare(all,prob,ids,ids,w,r,d);assert(tied.changed>0);++cases;
 bool fail=false;try{publish(tied,[](int,const void*,size_t){throw std::runtime_error("injected upload failure");});}catch(...){fail=true;}assert(fail);++cases;
 std::cout<<"PASS "<<cases<<" conservative diagnostic cases; actualvector selection uses savedggmlIDs, no expert override\n";
}
