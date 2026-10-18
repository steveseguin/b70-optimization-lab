#pragma once
// CPU fixture extension only: packet111's audit registry omits this inherited
// functor's sole unsigned member. Preserve its full type and capacity bytes.
#ifdef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet111-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet111-record-bundle/argument_block.hpp"
namespace p109 { struct SharedDown; }
namespace p105 { struct Pack; }
namespace p60 { template<int,bool,bool,bool,bool> struct Kernel; }
namespace p49dvirtual { template<unsigned> struct SmallKernel; }
namespace ownrt::arguments {
template<unsigned V>
std::vector<unsigned char> block(const p49dvirtual::SmallKernel<V>& op) {
 using T=p49dvirtual::SmallKernel<V>;
 std::vector<unsigned char> out;const char* type=typeid(T).name();
 out.insert(out.end(),type,type+std::strlen(type)+1);append(out,op.shapes);
 return out;
}
template<int Stage,bool Wide,bool Subgroup,bool Cached,bool Fused>
std::vector<unsigned char> block(const p60::Kernel<Stage,Wide,Subgroup,Cached,Fused>& op) {
 using T=p60::Kernel<Stage,Wide,Subgroup,Cached,Fused>;
 std::vector<unsigned char> out;const char* type=typeid(T).name();
 out.insert(out.end(),type,type+std::strlen(type)+1);append(out,op.capacity);
 return out;
}
template<class T> requires std::is_same_v<T,p109::SharedDown>
std::vector<unsigned char> block(const T& op) {
 std::vector<unsigned char> out;const char* type=typeid(T).name();
 out.insert(out.end(),type,type+std::strlen(type)+1);append(out,op.capacity);
 return out;
}
template<class T> requires std::is_same_v<T,p105::Pack>
std::vector<unsigned char> block(const T& op) {
 std::vector<unsigned char> out;const char* type=typeid(T).name();
 out.insert(out.end(),type,type+std::strlen(type)+1);
 append(out,op.rows);append(out,op.offset);return out;
}
}
#endif
