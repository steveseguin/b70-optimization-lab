#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet154-rank1-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p60_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet154-rank1-split/build/checked/experiments/own-xpu-runtime/stage2/packet154-rank1-split/performance.hpp"
namespace p60 {
using IDs=std::array<ownrt::Allocation,16>;
// Only numbered target layers; final HC and the MTP draft are untouched.
inline int stage(const std::string& label) {
 if(!label.starts_with("blk."))return -1;
 auto end=label.find('.',4);
 if(end==std::string::npos||end==4||label.find_first_not_of("0123456789",4)!=end)return -1;
 auto cls=label.substr(end+1);
 if(!cls.starts_with("hc.a.")&&!cls.starts_with("hc.f."))return -1;
 auto op=cls.substr(5);
 if(op=="norm")return 0;
 if(op=="low")return 1;
 if(op=="gate")return 2;
 if(op=="act"||op=="mix"||op=="inject")return 3;
 return -1;
}
integrated::Launch submit(ownrt::Device&,const IDs&,int,unsigned,bool wide=false,bool subgroup=false,bool cached=false,bool fused=false);
}
