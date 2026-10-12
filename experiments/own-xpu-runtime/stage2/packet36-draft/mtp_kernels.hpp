#pragma once
#include "performance.hpp"
namespace mtp36 {
// Draft-only requantisation of the official draft head; cannot change output.
struct Linear {
 ownrt::Allocation w{},peer{},x{},y{},py{},routes{},status{},ps{};
 unsigned rows{},columns{},batch=1,experts=1;bool int8=false,paired=false;
};
integrated::Launch elementwise(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
integrated::Launch linear(ownrt::Device&,const Linear&);
integrated::Launch norm_hidden(ownrt::Device&,ownrt::Allocation x,ownrt::Allocation gain,ownrt::Allocation y,ownrt::Allocation scratch,unsigned width);
integrated::Launch merge(ownrt::Device&,ownrt::Allocation hidden,ownrt::Allocation embedding,ownrt::Allocation streams,unsigned width);
}
