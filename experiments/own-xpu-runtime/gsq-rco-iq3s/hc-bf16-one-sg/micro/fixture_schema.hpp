#pragma once
#include <array>
#include <cstdint>
namespace micro {
// fixed.hpp is emitted exclusively only after authenticated extraction passes.
struct Fixed {unsigned layer,rows;const char *label,*weight,*shard,*x,*x_sha,*y,*y_sha,*packed,*weight_sha;uint64_t dev,ino,size,mtime,ctime;};
}
