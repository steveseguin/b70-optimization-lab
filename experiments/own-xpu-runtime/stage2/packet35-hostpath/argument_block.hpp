#pragma once
// CPU audit representation of the complete state of each captured host functor.
// Device functors retain their own unchanged native capture representation.
#ifdef OWN_RT_HOST_ONLY
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <typeinfo>
#include <stdexcept>
#include <vector>
namespace ownrt::arguments {
template<class> inline constexpr bool unsupported=false;
template<class T> void append(std::vector<unsigned char>& out,const T& value) {
 if constexpr(std::is_trivially_copyable_v<T>) {
  T copy=value;
#if defined(__GNUC__) && !defined(__clang__)
  // Compare member bytes, not indeterminate ABI padding. This does not change
  // the actual kernel/operation object, only this CPU audit copy.
  __builtin_clear_padding(&copy);
#else
  throw std::logic_error("CPU argument audit requires GCC clear_padding");
#endif
  const auto* p=reinterpret_cast<const unsigned char*>(&copy);out.insert(out.end(),p,p+sizeof(copy));
 }else if constexpr(requires {value.size();value.begin();value.end();}) {
  auto count=value.size();append(out,count);for(const auto& element:value)append(out,element);
 }else throw std::logic_error("unregistered argument member");
}
template<class T> std::vector<unsigned char> block(const T& op) {
 std::vector<unsigned char> out;
 // Type identity binds template parameters (kernel family, arithmetic, phase,
 // width and split) which have no per-instance data member.
 const char* type=typeid(T).name();out.insert(out.end(),type,type+std::strlen(type)+1);
 constexpr bool known=requires{op.matrices;}||requires{op.rows;}||requires{op.host;}||requires{op.b;}||requires{op.experts;}||requires{op.shape;}||requires{op.s;}||requires{op.spec;}||requires{op.n;};
 if constexpr(!known&&sizeof(T)!=sizeof(void*))throw std::logic_error("unregistered prepared operation state");
#define FIELD(name) if constexpr(requires{op.name;})append(out,op.name)
 FIELD(matrices);FIELD(variant);FIELD(shared);FIELD(rows);FIELD(host);FIELD(b);
 FIELD(experts);FIELD(shape);FIELD(s);FIELD(spec);FIELD(work);FIELD(mode);FIELD(n);
#undef FIELD
 return out;
}
}
#endif
