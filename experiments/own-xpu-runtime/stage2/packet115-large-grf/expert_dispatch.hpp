#pragma once
#include <vector>
#include <string_view>
namespace ownrt {class Device;}
namespace iq3::kopt2 {struct Matrix;}
namespace iq3::kopt3 {struct Launch;}
namespace integrated {using Matrix=iq3::kopt2::Matrix;using Launch=iq3::kopt3::Launch;}
namespace p39 {enum class Kind;struct Bindings;}
namespace p115 {
integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,p39::Kind,const p39::Bindings&,std::string_view,std::string_view);
}
