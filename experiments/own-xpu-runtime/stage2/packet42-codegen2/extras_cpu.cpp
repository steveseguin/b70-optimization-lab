#define OWN_RT_HOST_ONLY
#include "extras_core.hpp"
#include "extras_incumbent.hpp"
#define integrated tiny_reference_integrated
#define ng tiny_reference_ng
#define detmath tiny_reference_detmath
#define rope_constants tiny_reference_rope
#include "../packet29-merged/prototype/snapshot/reference.hpp"
#undef integrated
#undef ng
#undef detmath
#undef rope_constants
#include <iostream>
using namespace p42extras;
void reference(Fixture&f){tiny_reference_ng::Shape s;static_assert(sizeof(s)==sizeof(f.s));std::memcpy(&s,&f.s,sizeof s);tiny_reference_ng::Args a;for(int j=0;j<15;++j)a.p[j]=f.data[j].data();int ctrl[3];std::memcpy(ctrl,f.data[17].data(),4);std::memcpy(ctrl+1,f.data[18].data(),4);std::memcpy(ctrl+2,f.data[15].data(),4);a.p[15]=ctrl;tiny_reference_ng::reference::cpu(s,a);std::memcpy(f.data[15].data(),ctrl+2,4);}

void incumbent(Flat&f,bool alias=false,bool sched=false){p42extras_incumbent::Bound b{f.s,{}};auto p=f.pointers();if(alias)p[f.s.ni]=p[0];if(sched){auto x=scheduled(f);std::vector<void*>q;for(auto i:x.slots)q.push_back(p[i]);p=q;b.s=x.s;}std::copy(p.begin(),p.end(),b.p.begin());if(f.kind==Kind::streams||f.kind==Kind::combine||f.kind==Kind::ple_add){for(unsigned i=0;i<f.work();++i){if(f.kind==Kind::streams)p42extras_incumbent::simple_body<integrated::Op::hc_mix,0>(b,i);if(f.kind==Kind::combine)p42extras_incumbent::simple_body<integrated::Op::hc_combine,0>(b,i);if(f.kind==Kind::ple_add)p42extras_incumbent::simple_body<integrated::Op::ple_add,0>(b,i);}}else {std::vector<float>scratch(8192);p42extras_incumbent::simple(b,0,ng::HostTeam{scratch.data()});}}
void scheduled_core(Flat&f,bool alias=false){auto x=scheduled(f);auto p=f.pointers();if(alias)p[f.s.ni]=p[0];std::vector<void*>q;for(auto i:x.slots)q.push_back(p[i]);integrated::evaluate(x.s,q.data());}
int main(){try{auto v=fixtures();unsigned gates=0,refs=0,flatchecks=0,incumbentchecks=0,aliaschecks=0;uint64_t hash=1469598103934665603ull;
 for(auto&f:v){auto oracle=f;reference(oracle);auto incumbent=f;if(f.s.op==ng::select){std::vector<float>g(round2::scratch_floats(f.s));round2::cpu_stage<ng::select,0>(incumbent.s,incumbent.args(),g.data());round2::cpu_stage<ng::select,1>(incumbent.s,incumbent.args(),g.data());}else specialised::cpu(incumbent.s,incumbent.args());if(!oracle.equal(incumbent))throw std::runtime_error("extras incumbent/reference "+f.name);++refs;
 for(int w:{1,32,128,256}){auto out=f;if(w==1)cpu<1>(out);if(w==32)cpu<32>(out);if(w==128)cpu<128>(out);if(w==256)cpu<256>(out);if(!oracle.equal(out))throw std::runtime_error("extras geometry "+f.name);++gates;for(int j=0;j<19;++j)if(out.outputs[j])for(auto b:out.data[j])hash=(hash^b)*1099511628211ull;}}
 for(Kind k:{Kind::streams,Kind::combine,Kind::ple_add,Kind::check,Kind::commit,Kind::begin})for(unsigned n:{1u,3u,10u,17u,31u,640u,2560u,10240u})for(unsigned sc=0;sc<5;++sc){if(k==Kind::check&&n>32)continue;unsigned width=n>=2560?2560:n;Flat f(k,width,n,sc),ref=f;auto ptr=ref.pointers();integrated::evaluate(ref.s,ptr.data());auto inc=f;incumbent(inc);if(!inc.equal(ref))throw std::runtime_error("flat incumbent/core "+f.name);++incumbentchecks;auto sr=f,si=f;scheduled_core(sr);incumbent(si,false,true);if(!si.equal(ref)||!sr.equal(ref))throw std::runtime_error("scheduled incumbent/Core "+f.name);++incumbentchecks;for(int w:{1,32,256}){auto out=f;if(w==1)out.cpu<1>();if(w==32)out.cpu<32>();if(w==256)out.cpu<256>();if(!out.equal(ref))throw std::runtime_error("flat geometry "+f.name);++flatchecks;for(auto&d:out.data)for(auto b:d)hash=(hash^b)*1099511628211ull;}}
 for(Kind k:{Kind::combine,Kind::ple_add})for(unsigned n:{1u,3u,10u,17u,31u,640u,2560u,10240u})for(unsigned sc=0;sc<5;++sc){unsigned width=n>=2560?2560:n;Flat f(k,width,n,sc),ref=f,inc=f;auto p=ref.pointers();p[ref.s.ni]=p[0];integrated::evaluate(ref.s,p.data());incumbent(inc,true);if(inc.data[0]!=ref.data[0]||!inc.equal(ref))throw std::runtime_error("inplace incumbent/core "+f.name);++incumbentchecks;auto sr=f,si=f;scheduled_core(sr,true);incumbent(si,true,true);if(si.data[0]!=ref.data[0]||sr.data[0]!=ref.data[0]||!si.equal(ref)||!sr.equal(ref))throw std::runtime_error("scheduled inplace incumbent/Core "+f.name);++incumbentchecks;for(int w:{1,32,256}){auto out=f;if(w==1)out.cpu<1>(true);if(w==32)out.cpu<32>(true);if(w==256)out.cpu<256>(true);if(out.data[0]!=ref.data[0]||!out.equal(ref))throw std::runtime_error("inplace geometry "+f.name);++aliaschecks;for(auto b:out.data[0])hash=(hash^b)*1099511628211ull;}}
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"reference_checks\":"<<refs<<",\"fixture_checks\":"<<gates<<",\"flat_checks\":"<<flatchecks<<",\"incumbent_checks\":"<<incumbentchecks<<",\"alias_checks\":"<<aliaschecks<<",\"hash\":\""<<std::hex<<hash<<"\"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
