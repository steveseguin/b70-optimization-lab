// CPU fixture only (full-shape gate). Same audited member coverage for the S1
// small tuple as audit_small.hpp gives production p49dvirtual::SmallKernel<4>:
// the generic argument audit does not serialize a `shapes` member.
#ifdef OWN_RT_HOST_ONLY
namespace ownrt::arguments {
template<> inline std::vector<unsigned char> block(const p183::SmallKernel<4>& op) {
 std::vector<unsigned char> out;
 const char* type=typeid(p183::SmallKernel<4>).name();
 out.insert(out.end(),type,type+std::strlen(type)+1);
 append(out,op.shapes);
 return out;
}
}
#endif
