#pragma once
#include "p39_fused.hpp"
#include "p28/submit.hpp"
#include "runtime_kernels.hpp"
namespace p39 {
constexpr int plan_tag=3900;
struct Bindings {ownrt::Allocation other=0,out=0,streams=0,inject=0,mixture=0,shared_gate=0,one=0,error=0,active=0,position=0;unsigned capacity=0;bool indirect=false;};
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,Kind,const Bindings&);
}
