#pragma once
#include "performance.hpp"
#include <string_view>
namespace packet27::small {
// These names identify compile-time tuples, never device-side descriptors.
struct Shape { iq3::Type type; unsigned rows,columns,variant; };
std::vector<Shape> shapes(std::string_view name);
std::vector<std::string> names();
void validate(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
integrated::Launch submit(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
}
