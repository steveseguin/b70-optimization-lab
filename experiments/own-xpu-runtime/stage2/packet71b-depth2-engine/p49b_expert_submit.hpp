#pragma once
#include "p39_submit.hpp"
#include "p49b_gemv.hpp"
namespace p49b {
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,p39::Kind,const p39::Bindings&);
}
