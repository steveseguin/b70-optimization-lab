#include "p49d_submit.hpp"
#include "p100_down.hpp"
#include "p49c_submit.hpp"
#include "p49d_route.hpp"
#include "p78_route.hpp"
#include "p49d_recurrence.hpp"
#include "p82_recurrence.hpp"
#include "p82b_recurrence.hpp"
#include "p49d_mix.hpp"
#include "p49d_small.hpp"
#include "small_gemv.hpp"
#include <fstream>
#include <set>
#include <cctype>
#include "failure.hpp"
namespace p49d {
using integrated::Launch;using integrated::Spec;using ownrt::Allocation;using ownrt::Event;using ownrt::Device;
using IDs=std::span<const Allocation>;using Deps=std::span<const Event>;
Launch production(Device&d,const Spec&s,IDs a,Allocation c,Allocation sc,Allocation pr,Deps deps){return packet18::submit_parallel(d,s,a,c,sc,pr,deps);}
Launch production_route(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){return p49c::route_submit(d,s,a,deps);}
template<unsigned ExpWG>Launch route(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){return p49droute::submit<4,ExpWG>(d,s,a,deps);}
Launch route_fast(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){return p78route::submit(d,s,a,deps);}
// Validate the full production ABI before binding the fixed geometry candidate.
// The state input/output is the one intentional alias. Controls and all other
// writes stay disjoint, live and on this owner; no device reads are needed.
void recurrence_validate(Device&d,const Spec&s,IDs a,const p49drec::RecurrenceBindings&b){
 if(s.special!=integrated::Special::normal||s.fused_combine_norm||s.g.h!=2560||a.size()!=size_t(s.ni+s.no+s.nw+5))throw std::invalid_argument("p49d recurrence geometry/binding count");
 const size_t extents[]={10240,48,48,6144*128};
 for(unsigned i=0;i<4;++i)if(s.types[i]!=flash::Scalar::bf16||s.sizes[i]!=extents[i])throw std::invalid_argument("p49d recurrence input type/extent");
 for(unsigned i=0;i<2;++i)if(s.types[s.ni+i]!=flash::Scalar::bf16||s.sizes[s.ni+i]!=(i?6144*128:6144))throw std::invalid_argument("p49d recurrence output type/extent");
 if(s.grids[1]!=iq3::Type::F32&&s.grids[1]!=iq3::Type::BF16)throw std::invalid_argument("p49d recurrence gain type");
 if(s.ni==6)for(unsigned i=4;i<6;++i)if(s.types[i]!=flash::Scalar::u32||s.sizes[i]!=1)throw std::invalid_argument("p49d recurrence appended control type/extent");
 ng::validate(b.shape);auto bytes=ng::required_bytes(b.shape);
 for(unsigned i=0;i<19;++i){const auto&r=d.arena.row(b.ids[i]);unsigned align=(i==3||i==15||i==17||i==18||(i==4&&s.grids[1]==iq3::Type::F32))?4:2;if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes[i]||uintptr_t(r.pointer)%align)throw std::invalid_argument("p49d recurrence lifetime/extent/alignment");}
 for(unsigned out:{6u,7u,15u})for(unsigned j:{0u,1u,2u,3u,4u,5u,6u,7u,15u,17u,18u})if(out!=j&&b.ids[out]==b.ids[j]&&!(out==7&&j==5))throw std::invalid_argument("p49d recurrence output/control alias");
 if(b.ids[17]==b.ids[18])throw std::invalid_argument("p49d recurrence controls alias");
}
template<unsigned Rows>Launch recurrence(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){
 auto b=p49drec::recurrence_bindings(s,a);recurrence_validate(d,s,a,b);p49drec::RecurrenceKernel<Rows>k;k.shape=b.shape;auto e=d.compute(k,b.ids,deps);return {e,e,1};
}
template<bool Split>Launch recurrence82(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){
 auto b=p49drec::recurrence_bindings(s,a);recurrence_validate(d,s,a,b);p82rec::Kernel<Split>k;k.shape=b.shape;auto e=d.compute(k,b.ids,deps);return {e,e,1};
}
Launch recurrence82b(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){
 auto b=p49drec::recurrence_bindings(s,a);recurrence_validate(d,s,a,b);p82brec::Kernel<true> k;k.shape=b.shape;auto e=d.compute(k,b.ids,deps);return {e,e,1};
}
Launch mix(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){
 const unsigned tail=s.ni+s.no+s.nw;
 if(s.special!=integrated::Special::normal||s.fused_combine_norm||s.op!=integrated::Op::hc_mix||s.g.h!=2560||s.site.shape[1]!=2560||(s.ni!=2&&s.ni!=4)||s.no!=1||s.nw||a.size()!=tail+5||s.sizes[0]!=10240||s.sizes[1]!=10240||s.sizes[s.ni]!=2560)throw std::invalid_argument("p49d mix production shape");
 for(unsigned i:{0u,1u,unsigned(s.ni)})if(s.types[i]!=flash::Scalar::bf16)throw std::invalid_argument("p49d mix BF16 binding");
 if(s.ni==4){for(unsigned i=2;i<4;++i)if(s.types[i]!=flash::Scalar::u32||s.sizes[i]!=1)throw std::invalid_argument("p49d mix control shape");if(a[2]!=a[tail+3]||a[3]!=a[tail+1])throw std::invalid_argument("p49d mix duplicate controls");}
 if(s.g.context<=0)throw std::invalid_argument("p49d mix context");
 for(unsigned i=0;i<a.size();++i){const auto&r=d.arena.row(a[i]);size_t need=i<tail?s.sizes[i]*flash::scalar_bytes(s.types[i]):i<tail+4?4:2;unsigned align=(i==tail+1||i==tail+2||i==tail+3)?4:2;if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<need||uintptr_t(r.pointer)%align)throw std::invalid_argument("p49d mix lifetime/extent/alignment");}
 for(unsigned output:{unsigned(s.ni),tail+1})for(unsigned j=0;j<a.size();++j)if(j!=output&&a[j]==a[output]&&!(output==tail+1&&s.ni==4&&j==3))throw std::invalid_argument("p49d mix output/control alias");
 if(a[tail+2]==a[tail+3])throw std::invalid_argument("p49d mix controls alias");
 p49dmix::Kernel k;k.spec=s;auto e=d.compute(k,a,deps);return {e,e,1};
}
Submit resolve(std::string_view cls,std::string_view choice){
 if(cls=="other_fusion"&&(choice=="production"||choice=="fused"))return production;
 if(cls=="head"&&(choice=="production"||choice=="head-transpose"||choice=="head-split-81920"||choice=="head-split-122880"||choice=="head-split-compute"||choice=="head-split-bcs"))return production;
 if(cls=="host_retire"&&(choice=="production"||choice=="ordered"||choice=="reply-first"))return production;
 if(cls=="hc_norm"&&(choice=="production"||choice=="subgroup"||choice=="consumer"))return production;
 if(cls=="hc_gate"&&(choice=="production"||choice=="wide"))return production;
 if(cls=="packed_dense"&&(choice=="production"||choice=="head-packed"||choice=="dense-packed"||choice=="combined"))return production;
 if(cls=="experts"){
  choice=p100::gate_choice(choice);
 }
 if(cls=="experts"&&(choice=="production"||choice=="wg64"||choice=="wg128"||choice=="prefetch64"||choice=="wide64"||choice=="experts2-a"||choice=="experts2-b"||choice=="input-packed"||choice=="gate-input-packed"||choice=="down-input-packed"||choice=="exp-halfcache"||choice=="exp-grid-prefetch"||choice=="exp-grid-prefetch+halfcache"))return production;
 if(cls=="miss"&&(choice=="control"||choice=="batch"))return production;
 if(cls=="route"){if(choice=="route-fast")return route_fast;if(choice=="production")return production_route;if(choice=="route-rank4")return route<256>;if(choice=="route-exp32-rank4")return route<32>;}
 if(cls=="recurrence"){if(choice=="rec-both")return recurrence82<true>;if(choice=="rec-both-plus")return recurrence82b;if(choice=="rec-gates")return recurrence82<false>;if(choice=="rec-parallel")return recurrence82<true>;if(choice=="production")return production;if(choice=="rows4-shared")return recurrence<4>;if(choice=="rows8-shared")return recurrence<8>;}
 if(cls=="hc"){if(choice=="production")return production;if(choice=="mix-vector4")return mix;}
 throw std::invalid_argument("p49d unregistered selection");
}
Submit Selection::site(const Spec&s)const{
 if(s.op==integrated::Op::route)return resolve("route",choices.at("route"));
 if(s.op==integrated::Op::gdn)return resolve("recurrence",choices.at("recurrence"));
 if(s.op==integrated::Op::hc_mix&&s.special==integrated::Special::normal)return resolve("hc",choices.at("hc"));
 return production;
}
void Selection::load(const std::string&path,const std::string&expected_sha256){
 std::ifstream f(path);if(!f)throw std::invalid_argument("p49d selection file missing");std::string text((std::istreambuf_iterator<char>(f)),{});size_t at=0;
 const auto digest=packet26::hash(text.data(),text.size());
 if(!expected_sha256.empty()&&digest!=expected_sha256)throw std::invalid_argument("p49d selection bytes differ from sealed SHA256");
 auto ws=[&]{while(at<text.size()&&std::isspace(static_cast<unsigned char>(text[at])))++at;};
 auto take=[&](char c){ws();if(at>=text.size()||text[at++]!=c)throw std::invalid_argument("p49d selection punctuation");};
 auto str=[&]{take('"');std::string v;while(at<text.size()&&text[at]!='"'){auto c=text[at++];if(c==92||static_cast<unsigned char>(c)<32)throw std::invalid_argument("p49d selection string");v+=c;}take('"');return v;};
 auto more=[&]{ws();if(at<text.size()&&text[at]==','){++at;return true;}return false;};
 std::set<std::string>fields;std::map<std::string,std::string>values,draft_values;take('{');
 do{
  auto k=str();if(!fields.insert(k).second)throw std::invalid_argument("p49d duplicate selection field");take(':');
  if(k=="schema"){
   if(str()!="packet59c.selection.v1")throw std::invalid_argument("p49d selection schema");
  }else if(k=="choices"){
   take('{');do{auto cls=str();take(':');auto value=str();resolve(cls,value);if(!values.emplace(cls,value).second)throw std::invalid_argument("p49d duplicate selection class");}while(more());take('}');
  }else if(k=="draft"){
   take('{');do{auto key=str();take(':');if(!draft_values.emplace(key,str()).second)throw std::invalid_argument("p59c duplicate draft key");}while(more());take('}');
  }else if(k=="decision"){
   ws();if(text.compare(at,4,"null")==0)at+=4;
   else {
    std::map<std::string,std::string>decision;take('{');do{auto key=str();take(':');if(!decision.emplace(key,str()).second)throw std::invalid_argument("p49d duplicate decision field");}while(more());take('}');
    if(decision.size()!=2||!decision.contains("path")||!decision.contains("sha256")||decision.at("path")!="selection-decision.json")throw std::invalid_argument("p49d decision binding");
    const auto&digest=decision.at("sha256");if(digest.size()!=64||digest.find_first_not_of("0123456789abcdef")!=std::string::npos)throw std::invalid_argument("p49d decision digest");
   }
  }else throw std::invalid_argument("p49d unknown selection field");
 }while(more());take('}');ws();
 if(at!=text.size()||fields!=std::set<std::string>{"schema","choices","decision","draft"}||values.size()!=11||!values.contains("head"))throw std::invalid_argument("p49d incomplete/trailing selection");
 p59c::validate(draft_values);
 auto target_values=values;target_values.erase("other_fusion");target_values.erase("head");target_values.erase("host_retire");target_values.erase("hc_norm");if(target_values.at("route")=="route-fast")target_values["route"]="route-exp32-rank4";target_values.erase("miss");target_values.erase("experts");target_values.erase("packed_dense");target_values.erase("hc_gate");
 if(target_values.at("recurrence")=="rec-both"||target_values.at("recurrence")=="rec-both-plus"||target_values.at("recurrence")=="rec-gates"||target_values.at("recurrence")=="rec-parallel")target_values["recurrence"]="rows4-shared";
 if(target_values!=std::map<std::string,std::string>{{"route","route-exp32-rank4"},{"recurrence","rows4-shared"},{"hc","production"}})throw std::invalid_argument("p59c target must stay packet56");
 choices=std::move(values);draft=std::move(draft_values);observed_sha256=digest;
}
Launch small(Device&d,std::string_view name,std::span<const integrated::Matrix>ms,std::span<const unsigned>variants){
 if(name!="small.ffn.q6")throw std::invalid_argument("p49d only banked small.ffn.q6 tuple");packet27::small::validate(d,name,ms,variants);
 p49dvirtual::SmallKernel<4>k;std::array<Allocation,12>ids{};
 for(unsigned i=0;i<4;++i){const auto&m=ms[i];k.shapes[i].rows=m.rows;k.shapes[i].rb=integrated::arithmetic::row_bytes(m.type,m.columns,variants[i]);ids[3*i]=m.w;ids[3*i+1]=m.x;ids[3*i+2]=m.y;}
 auto e=d.compute(k,ids,{});return {e,e,1};
}
} // namespace p49d
