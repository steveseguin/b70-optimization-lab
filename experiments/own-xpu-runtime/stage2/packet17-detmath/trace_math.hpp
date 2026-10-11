#pragma once
// Host-only capture of every distinct native elementary input used by v1 core.
#include <bit>
#include <cmath>
#include <cstdint>
#include <set>
namespace trace_math {
inline std::set<uint64_t> calls;
inline void record(unsigned op,float x){calls.insert((uint64_t(op)<<32)|std::bit_cast<uint32_t>(x));}
inline float exp(float x){record(0,x);return std::exp(x);}
inline float log(float x){record(1,x);return std::log(x);}
inline float sqrt(float x){record(2,x);return std::sqrt(x);}
inline float rsqrt(float x){record(3,x);record(8,x);record(9,x);float r=sqrt(x);record(4,r);return 1.f/r;}
inline float recip(float x){record(4,x);return 1.f/x;}
inline float sin(float x){record(5,x);return std::sin(x);}
inline float cos(float x){record(6,x);return std::cos(x);}
inline float pow(float x,float y){if(x!=1e7f)__builtin_trap();record(7,y);return std::pow(x,y);}
}
