#pragma once
#include "tiny_fixture.hpp"
#include "../packet29-merged/round2.hpp"
#include "../packet29-merged/adapter.hpp"
namespace p42extras {
using p42tiny::Fixture;
inline std::vector<Fixture> fixtures(){std::vector<Fixture> v;auto dir=std::filesystem::path(__FILE__).parent_path()/"../packet29-merged/build/fusion-fixtures";for(auto&p:std::filesystem::directory_iterator(dir))if(p.path().extension()==".fixture"){std::ifstream f(p.path(),std::ios::binary);ng::Shape s;f.read(reinterpret_cast<char*>(&s),sizeof s);if(s.op==ng::norm||s.op==ng::combine_norm||s.op==ng::select)v.emplace_back(p.path());}auto found=std::find_if(v.begin(),v.end(),[](auto&f){return f.name=="qsa-select-1.fixture";});if(found==v.end())throw std::runtime_error("existing select fixture missing");auto full=*found;full.s.capacity=256;full.name="qsa-select-cap256-1.fixture";auto old=full.data[1];full.data[1].resize(ng::required_bytes(full.s)[1]);for(size_t i=0;i<full.data[1].size();++i)full.data[1][i]=old[i%old.size()];full.data[17]=Fixture::integer(255);v.push_back(std::move(full));std::sort(v.begin(),v.end(),[](auto&a,auto&b){return a.name<b.name;});return v;}
template<int WG>void cpu(Fixture&f){auto s=f.s;auto a=f.args();if(s.op==ng::select){std::vector<float> local(round2::local_floats(s)),global(round2::scratch_floats(s));for(int g=0;g<round2::groups(s);++g)round2::group<ng::select,0>(s,a,g,global.data(),p42tiny::CpuTeam<WG>{local.data()});for(int g=0;g<round2::groups(s);++g)round2::group<ng::select,1>(s,a,g,global.data(),p42tiny::CpuTeam<WG>{local.data()});}
 else{std::vector<float> scratch(specialised::scratch_floats(s));auto stage=[&]<int Stage>(){p42tiny::mapping<WG>(specialised::work_items(s,Stage),[&](size_t i){if(s.op==ng::norm)specialised::body<ng::norm,Stage>(s,a,i,scratch.data(),specialised::HostGuard{});else specialised::body<ng::combine_norm,Stage>(s,a,i,scratch.data(),specialised::HostGuard{});});};stage.template operator()<0>();stage.template operator()<1>();}}
enum class Kind{streams,combine,ple_add,check,commit,begin};
struct Compact{std::array<integrated::View,3>in{};integrated::View out{};uint32_t*error;uint32_t*position;const uint32_t*active;unsigned width=2560,context=128;};
template<Kind K,class Guard>void leaf(Compact b,unsigned j,Guard guard){
 if(!*b.active)return;
 if constexpr(K==Kind::begin){if(j==0&&*b.position>=b.context)guard.fail(b.error);return;}
 if(guard.error(b.error))return;
 if constexpr(K==Kind::commit){if(j==0)++*b.position;}
 if constexpr(K==Kind::streams)b.out.put(j,b.in[0].get(j%b.in[0].n));
 if constexpr(K==Kind::combine)b.out.put(j,b.in[0].get(j)+b.in[1].get(j%b.width)*(2.f*ng::sigmoid(b.in[2].get(j/b.width)/4.f)));
 if constexpr(K==Kind::ple_add)b.out.put(j,b.in[0].get(j)+ng::Args::bf(b.in[1].get(j)+b.in[2].get(j)));
 if constexpr(K==Kind::check){if(j)return;float v[32]{};for(unsigned k=0;k<b.in[0].n;++k)v[k]=float(b.in[0].get(k)!=0);for(unsigned stride=1;stride<b.in[0].n;stride*=2)for(unsigned k=0;k<b.in[0].n;k+=2*stride)v[k]=v[k]+(k+stride<b.in[0].n?v[k+stride]:0.f);if(v[0])guard.fail(b.error);}
}
struct CpuGuard{unsigned error(uint32_t*p)const{return *p;}void fail(uint32_t*p)const{*p=1;}};
struct Flat{
 integrated::Spec s;Kind kind;std::vector<std::vector<uint8_t>>data;std::string name;
 Flat(Kind k,unsigned width,unsigned n,unsigned scenario):kind(k){using namespace integrated;if(k==Kind::combine)n=4*width;s.g.context=128;s.g.h=width;s.implementation=1;s.site.shape[1]=width;s.op=k==Kind::combine?Op::hc_combine:k==Kind::ple_add?Op::ple_add:Op::norm;s.special=k==Kind::streams?Special::broadcast:k==Kind::commit?Special::commit:k==Kind::begin?Special::begin:k==Kind::check?Special::check_status:Special::normal;s.ni=(k==Kind::combine||k==Kind::ple_add)?3:k==Kind::commit||k==Kind::begin?0:1;s.no=k==Kind::commit||k==Kind::begin||k==Kind::check?0:1;
  for(int j=0;j<s.ni+s.no;++j){s.types[j]=k==Kind::check?flash::Scalar::u32:flash::Scalar::bf16;s.sizes[j]=j==s.ni?n:k==Kind::check?n:k==Kind::streams?width:k==Kind::combine?(j==0?n:j==1?width:(n+width-1)/width):n;data.emplace_back(std::max(size_t(4),s.sizes[j]*flash::scalar_bytes(s.types[j])));integrated::View v{data.back().data(),s.sizes[j],s.types[j]};for(unsigned i=0;i<s.sizes[j];++i)v.put(i,k==Kind::check?0:float(int((i*13+j*7)%31)-15)*.03125f);}
  data.emplace_back(128*1024*4);data.emplace_back(4);data.emplace_back(4);data.emplace_back(4);data.emplace_back(4);*reinterpret_cast<uint32_t*>(data[tail()+3].data())=1;
  if(scenario==1)*reinterpret_cast<uint32_t*>(data[tail()+3].data())=0;if(scenario==2)*reinterpret_cast<uint32_t*>(data[tail()+1].data())=7;if(scenario==3)*reinterpret_cast<uint32_t*>(data[tail()+2].data())=(k==Kind::combine||k==Kind::ple_add)?127:128;if(scenario==4&&s.ni){integrated::View v{data[0].data(),s.sizes[0],s.types[0]};v.put(s.sizes[0]-1,k==Kind::check?1:INFINITY);}name=std::to_string(int(k))+"-"+std::to_string(width)+"-"+std::to_string(n)+"-"+std::to_string(scenario);
 }
 unsigned tail()const{return s.ni+s.no+s.nw;}
 std::vector<void*> pointers(){std::vector<void*>p;for(auto&v:data)p.push_back(v.data());return p;}
 Compact bind(){Compact c;for(int j=0;j<s.ni;++j)c.in[j]={data[j].data(),s.sizes[j],s.types[j]};if(s.no)c.out={data[s.ni].data(),s.sizes[s.ni],s.types[s.ni]};c.error=reinterpret_cast<uint32_t*>(data[tail()+1].data());c.position=reinterpret_cast<uint32_t*>(data[tail()+2].data());c.active=reinterpret_cast<uint32_t*>(data[tail()+3].data());c.width=s.site.shape[1];c.context=s.g.context;return c;}
 bool equal(const Flat&b)const{for(int j=s.ni;j<s.ni+s.no;++j)if(data[j]!=b.data[j])return false;return data[tail()+1]==b.data[tail()+1]&&data[tail()+2]==b.data[tail()+2];}
 unsigned work()const{return s.no?unsigned(s.sizes[s.ni]):1;}
 template<int WG>void cpu(bool alias=false){auto b=bind();if(alias)b.out=b.in[0];p42tiny::mapping<WG>(work(),[&](size_t j){switch(kind){case Kind::streams:leaf<Kind::streams>(b,j,CpuGuard{});break;case Kind::combine:leaf<Kind::combine>(b,j,CpuGuard{});break;case Kind::ple_add:leaf<Kind::ple_add>(b,j,CpuGuard{});break;case Kind::check:leaf<Kind::check>(b,j,CpuGuard{});break;case Kind::commit:leaf<Kind::commit>(b,j,CpuGuard{});break;case Kind::begin:leaf<Kind::begin>(b,j,CpuGuard{});break;}});}
};
// Exact plan.hpp scheduled ABI: controls may also be explicit inputs/outputs.
struct Scheduled{integrated::Spec s;std::vector<unsigned>slots;};
inline Scheduled scheduled(const Flat&f){Scheduled x;x.s=f.s;unsigned t=f.tail();auto input=[&](unsigned slot){x.slots.push_back(slot);};
 if(f.kind==Kind::begin){input(t+3);input(t+2);x.s.ni=2;}
 else if(f.kind==Kind::commit){input(t+1);input(t+3);input(t+2);x.s.ni=3;}
 else if(f.kind==Kind::check){input(0);input(t+1);input(t+3);x.s.ni=3;}
 else {for(int j=0;j<f.s.ni;++j)input(j);input(t+3);input(t+1);x.s.ni=f.s.ni+2;}
 x.s.no=1;input(f.kind==Kind::commit?t+2:(f.kind==Kind::begin||f.kind==Kind::check)?t+1:f.s.ni);
 for(unsigned j=0;j<x.slots.size();++j){auto slot=x.slots[j];x.s.sizes[j]=slot<t?f.s.sizes[slot]:1;x.s.types[j]=slot<t?f.s.types[slot]:flash::Scalar::u32;}
 for(unsigned j=t;j<t+5;++j)input(j);return x;
}

}
