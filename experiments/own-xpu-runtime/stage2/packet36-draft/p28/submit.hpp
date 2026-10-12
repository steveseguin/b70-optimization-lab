#pragma once
#include "registry.hpp"
namespace p28 {
struct Bound {
 const uint8_t* w{};const uint8_t* peer{};const uint16_t* x{};uint16_t* y{};uint16_t* py{};
 const iq3::Route* routes{};uint32_t* status{};uint32_t* ps{};float* scratch{};
 size_t rb{};unsigned rows{},count{},experts{},split{};bool paired{},has_routes{};
};
static_assert(sizeof(Bound)<=1024,"packet28 arguments exceed 1024 bytes");
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"packet28 kernel capture exceeds 1024 bytes");return f;}
void validate(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned);
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned);
}
