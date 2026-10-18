#pragma once
#include "p104_mtp.hpp"
#include "p104_shared.hpp"
namespace p104draftsubmit {
inline void extent(ownrt::Device&d,ownrt::Allocation a,size_t n,unsigned alignment){const auto&r=d.arena.row(a);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n||uintptr_t(r.pointer)%alignment)throw std::invalid_argument("p104 draft extent/alignment/lifetime");}
template<unsigned K,bool I,bool Pair>inline integrated::Launch issue(ownrt::Device&d,const mtp36::Linear&a){
 p104mtp::Dense<K,I,Pair>op;op.a=a;
 std::array<ownrt::Allocation,8>ids{a.w,Pair?a.peer:a.w,a.x,a.y,Pair?a.py:a.y,a.routes?a.routes:a.x,a.status?a.status:a.y,a.ps?a.ps:a.y};
 auto e=d.compute(op,ids,{});return {e,e,1};
}
inline integrated::Launch linear(ownrt::Device&d,const mtp36::Linear&a){
 if(a.rows%16||!a.rows||a.columns%16||!a.experts||a.experts>512||!a.batch||a.batch>10||(a.paired&&!a.routes)||(!a.routes&&(a.experts!=1||a.batch!=1))||(a.int8!=bool(a.routes)))throw std::invalid_argument("p104 draft layout shape");
 if((a.columns==2560&&a.rows!=640)||(a.columns==640&&a.rows!=2560)||(a.columns!=2560&&a.columns!=640))throw std::invalid_argument("p104 draft unregistered projection");
 size_t rb=a.int8?a.columns+a.columns/16*4:a.columns*2,n=size_t(a.rows)*a.batch;
 extent(d,a.w,size_t(a.experts)*a.rows*rb,16);extent(d,a.x,size_t(a.paired?1:a.batch)*a.columns*2,2);extent(d,a.y,n*2,2);
 if(a.routes){extent(d,a.routes,a.batch*sizeof(iq3::Route),4);extent(d,a.status,a.batch*4,4);}
 if(a.paired){extent(d,a.peer,size_t(a.experts)*a.rows*rb,16);extent(d,a.py,n*2,2);extent(d,a.ps,a.batch*4,4);}
 std::vector<ownrt::Allocation>reads{a.w,a.x};if(a.routes)reads.push_back(a.routes);if(a.paired)reads.push_back(a.peer);
 std::vector<ownrt::Allocation>writes{a.y};if(a.routes)writes.push_back(a.status);if(a.paired){writes.push_back(a.py);writes.push_back(a.ps);}
 for(size_t i=0;i<writes.size();++i){for(auto r:reads)if(writes[i]==r)throw std::invalid_argument("p104 draft read/write alias");for(size_t j=0;j<i;++j)if(writes[i]==writes[j])throw std::invalid_argument("p104 draft output alias");}
 if(!a.int8&&a.columns==640){p104shared::Kernel<0,iq3::Type::BF16,640,1>op;op.b.rows=a.rows;op.b.count=1;op.b.experts=1;op.b.rb=rb;
  std::array<ownrt::Allocation,9>ids{a.w,a.w,a.x,a.y,a.y,a.x,a.y,a.y,a.y};auto e=d.compute(op,ids,{});return {e,e,1};}
 if(a.columns==2560){if(a.int8){if(!a.paired)throw std::invalid_argument("p104 draft gate must be paired");return issue<2560,true,true>(d,a);}return issue<2560,false,false>(d,a);}
 if(!a.int8||a.paired)throw std::invalid_argument("p104 draft down layout");return issue<640,true,false>(d,a);
}
}
