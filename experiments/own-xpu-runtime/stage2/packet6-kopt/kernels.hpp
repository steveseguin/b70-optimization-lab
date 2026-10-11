#pragma once
#include "../packet2/kernels/device.hpp"
namespace iq3::kopt {
struct Matrix {
  Type type;ownrt::Allocation w,x,y;size_t rows,columns;
  Type activation=Type::BF16,output_type=Type::BF16;
  ownrt::Allocation fp32=0;
};
ownrt::Event gemv(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,size_t,size_t,
                  Type=Type::BF16,Type=Type::BF16,unsigned=16,ownrt::Allocation=0);
ownrt::Event routed_gemv(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,
                         ownrt::Allocation,ownrt::Allocation,uint32_t,uint32_t,size_t,uint32_t,uint32_t,
                         Type=Type::BF16,Type=Type::BF16,unsigned=16,ownrt::Allocation=0);
// Independent inputs only: this does not fuse across real activation dependencies.
ownrt::Event fused_gemv(ownrt::Device&,const std::vector<Matrix>&,unsigned=16);
// Populated only inside a coordinator-authorized submit; never enumerates.
std::string device_properties();
}
