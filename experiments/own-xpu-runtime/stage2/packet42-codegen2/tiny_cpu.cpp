#define OWN_RT_HOST_ONLY
#include "tiny_fixture.hpp"
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
using namespace p42tiny;
void reference(Fixture&f){tiny_reference_ng::Shape s;static_assert(sizeof(s)==sizeof(f.s));std::memcpy(&s,&f.s,sizeof s);tiny_reference_ng::Args a;for(int j=0;j<15;++j)a.p[j]=f.data[j].data();if(f.alias_history)a.p[4]=a.p[1];int ctrl[3];std::memcpy(ctrl,f.data[17].data(),4);std::memcpy(ctrl+1,f.data[18].data(),4);std::memcpy(ctrl+2,f.data[15].data(),4);a.p[15]=ctrl;tiny_reference_ng::reference::cpu(s,a);std::memcpy(f.data[15].data(),ctrl+2,4);}
template<int WG>void candidate(Fixture&f){switch(f.s.op){case ng::conv:cpu<ng::conv,WG>(f.s,f.args());break;case ng::activation:cpu<ng::activation,WG>(f.s,f.args());break;case ng::mix:cpu<ng::mix,WG>(f.s,f.args());break;case ng::moe_combine:cpu<ng::moe_combine,WG>(f.s,f.args());break;default:cooperative_cpu<WG>(f.s,f.args());break;}}
int main(int argc,char**){try{auto v=argc>1?std::vector<Fixture>{}:fixtures();for(int op:{ng::conv,ng::activation,ng::mix,ng::moe_combine})for(int width:{1,17,31,33,127,129,640,2560})for(int scenario=0;scenario<6;++scenario){if(argc>1&&(op!=ng::activation||width!=1||scenario!=5))continue;ng::Shape s{};s.op=op;s.width=width;s.extra=op==ng::moe_combine?10:1;Fixture f(s,"odd-control-op"+std::to_string(op)+"-w"+std::to_string(width)+"-scenario"+std::to_string(scenario));if(scenario==1)f.data[18]=Fixture::integer(0);if(scenario==2)f.data[15]=Fixture::integer(7);if(scenario==3)f.data[17]=Fixture::integer(-1);if(scenario==4)f.data[17]=Fixture::integer(s.capacity);if(scenario==5){uint16_t v=0x7fc1;std::memcpy(f.data[0].data(),&v,2);}v.push_back(f);}unsigned checks=0,refs=0;uint64_t hash=1469598103934665603ull;
 for(auto&f:v){auto incumbent=f;ng::cpu(incumbent.s,incumbent.args());auto ref=f;reference(ref);if(!incumbent.equal(ref)){for(int j=0;j<19;++j)if(f.outputs[j]&&incumbent.output_bytes(j)!=ref.output_bytes(j))std::cerr<<"slot "<<j<<" incumbent "<<unsigned(incumbent.output_bytes(j)[0])<<","<<unsigned(incumbent.output_bytes(j)[1])<<" reference "<<unsigned(ref.output_bytes(j)[0])<<","<<unsigned(ref.output_bytes(j)[1])<<"\n";throw std::runtime_error("incumbent/reference "+f.name);}++refs;for(int shape:{1,32,256}){auto candidate_fixture=f;if(shape==1)candidate<1>(candidate_fixture);else if(shape==32)candidate<32>(candidate_fixture);else candidate<256>(candidate_fixture);if(!incumbent.equal(candidate_fixture))throw std::runtime_error("geometry bytes "+f.name);++checks;for(int j=0;j<19;++j)if(f.outputs[j])for(auto b:candidate_fixture.output_bytes(j))hash=(hash^b)*1099511628211ull;}}
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"fixture_count\":"<<v.size()<<",\"reference_checks\":"<<refs<<",\"geometry_checks\":"<<checks<<",\"output_fnv64\":\""<<std::hex<<hash<<"\"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
