#pragma once
#include "adapter.hpp"
#include "p59c_select.hpp"
#include "p39_submit.hpp"
#include <map>
#include <string_view>
namespace p49d {
using Submit=integrated::Launch(*)(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,std::span<const ownrt::Event>);
Submit resolve(std::string_view cls,std::string_view choice);
struct Selection {
 std::map<std::string,std::string> choices{{"route","production"},{"recurrence","production"},{"hc","production"}};
 std::map<std::string,std::string> draft=p59c::defaults();
 std::string observed_sha256;
 void load(const std::string& path,const std::string& expected_sha256="");
 Submit site(const integrated::Spec&)const;
};
integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,p39::Kind,const p39::Bindings&);
integrated::Launch small(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
} // namespace p49d
