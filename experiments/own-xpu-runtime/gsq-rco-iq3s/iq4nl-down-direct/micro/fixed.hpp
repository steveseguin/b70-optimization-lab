#pragma once
#include <array>
#include <cstdint>
namespace micro {
struct Fixed {unsigned layer;const char *label,*weight,*shard,*x,*x_sha,*routes,*routes_sha,*y,*y_sha,*status,*status_sha,*slices,*slices_sha;uint64_t dev,ino,size,mtime,ctime;unsigned used;std::array<unsigned,10> ids;};
inline constexpr std::array<Fixed,1> fixed{{
{0,"blk.0.expsdown","blk.0.ffn_down_exps.weight","/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf","/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/iq4nl-down-direct/micro/fixtures/blk.0.expsdown-input.bin","0835593250ae1d154aa93219610feafd4127e830dd5f42804d78fd2a80fc8f2e","/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/iq4nl-down-direct/micro/fixtures/blk.0.expsdown-routes.bin","a460d0e95a8aec3c298bd15c1b81fb4f4746b5ccac4065ff6e4bc53081c32145","/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/iq4nl-down-direct/micro/fixtures/blk.0.expsdown-output.bin","d270a98910e8ef15cc9d687ecfb9cc59a2b5ab96ed2c02b58b3a43225f1d20d9","/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/iq4nl-down-direct/micro/fixtures/blk.0.expsdown-status.bin","2c34ce1df23b838c5abf2a7f6437cca3d3067ed509ff25f11df6b11b582b51eb","/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/iq4nl-down-direct/micro/fixtures/blk.0.expsdown-slices.bin","4184b818d014e745b01a8f233cb69f9a5f5b19081a191d3c3636e919d9f3003b",2050ULL,2778523ULL,55063448064ULL,1792814866970869300ULL,1792814960708461300ULL,10,{57,125,142,150,204,225,230,313,428,474}},
}};
}
