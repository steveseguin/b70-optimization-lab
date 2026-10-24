#pragma once
#include <string_view>
namespace iq3block {
inline bool selected(std::string_view label,std::string_view weight){
 return (label=="blk.0.expsgate"&&weight=="blk.0.ffn_gate_exps.weight") ||
        (label=="blk.0.expsup"&&weight=="blk.0.ffn_up_exps.weight") ||
        (label=="blk.7.expsgate"&&weight=="blk.7.ffn_gate_exps.weight") ||
        (label=="blk.7.expsup"&&weight=="blk.7.ffn_up_exps.weight") ||
        (label=="blk.12.expsgate"&&weight=="blk.12.ffn_gate_exps.weight") ||
        (label=="blk.12.expsup"&&weight=="blk.12.ffn_up_exps.weight") ||
        (label=="blk.14.expsgate"&&weight=="blk.14.ffn_gate_exps.weight") ||
        (label=="blk.14.expsup"&&weight=="blk.14.ffn_up_exps.weight") ||
        (label=="blk.16.expsgate"&&weight=="blk.16.ffn_gate_exps.weight") ||
        (label=="blk.16.expsup"&&weight=="blk.16.ffn_up_exps.weight") ||
        (label=="blk.18.expsgate"&&weight=="blk.18.ffn_gate_exps.weight") ||
        (label=="blk.18.expsup"&&weight=="blk.18.ffn_up_exps.weight") ||
        (label=="blk.20.expsgate"&&weight=="blk.20.ffn_gate_exps.weight") ||
        (label=="blk.20.expsup"&&weight=="blk.20.ffn_up_exps.weight") ||
        (label=="blk.22.expsgate"&&weight=="blk.22.ffn_gate_exps.weight") ||
        (label=="blk.22.expsup"&&weight=="blk.22.ffn_up_exps.weight") ||
        (label=="blk.30.expsgate"&&weight=="blk.30.ffn_gate_exps.weight") ||
        (label=="blk.30.expsup"&&weight=="blk.30.ffn_up_exps.weight") ||
        (label=="blk.31.expsgate"&&weight=="blk.31.ffn_gate_exps.weight") ||
        (label=="blk.31.expsup"&&weight=="blk.31.ffn_up_exps.weight") ||
        (label=="blk.33.expsgate"&&weight=="blk.33.ffn_gate_exps.weight") ||
        (label=="blk.33.expsup"&&weight=="blk.33.ffn_up_exps.weight") ||
        (label=="blk.37.expsgate"&&weight=="blk.37.ffn_gate_exps.weight") ||
        (label=="blk.37.expsup"&&weight=="blk.37.ffn_up_exps.weight") ||
        (label=="blk.38.expsgate"&&weight=="blk.38.ffn_gate_exps.weight") ||
        (label=="blk.38.expsup"&&weight=="blk.38.ffn_up_exps.weight") ||
        (label=="blk.41.expsgate"&&weight=="blk.41.ffn_gate_exps.weight") ||
        (label=="blk.41.expsup"&&weight=="blk.41.ffn_up_exps.weight") ||
        (label=="blk.42.expsgate"&&weight=="blk.42.ffn_gate_exps.weight") ||
        (label=="blk.42.expsup"&&weight=="blk.42.ffn_up_exps.weight") ||
        (label=="blk.43.expsgate"&&weight=="blk.43.ffn_gate_exps.weight") ||
        (label=="blk.43.expsup"&&weight=="blk.43.ffn_up_exps.weight") ||
        (label=="blk.46.expsgate"&&weight=="blk.46.ffn_gate_exps.weight") ||
        (label=="blk.46.expsup"&&weight=="blk.46.ffn_up_exps.weight");
}
}
