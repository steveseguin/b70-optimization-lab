// CPU fixture only. Packet103's generic argument audit omits SmallKernel.shapes.
// Match packet109's audited member coverage without changing frozen headers.
#ifdef OWN_RT_HOST_ONLY
namespace ownrt::arguments {
template<> inline std::vector<unsigned char> block(const p49dvirtual::SmallKernel<4>& op) {
 std::vector<unsigned char> out;
 const char* type=typeid(p49dvirtual::SmallKernel<4>).name();
 out.insert(out.end(),type,type+std::strlen(type)+1);
 append(out,op.shapes);
 return out;
}
}
#endif
