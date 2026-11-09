// Shared decode-trace tags (cpu_run_v41 reference <-> own_run_v41 device).
#pragma once
enum TraceTag {
    TT_EMBED = 1, TT_ENGRAM, TT_ATTN_MIX_PRE, TT_ATTN_MIX_POST, TT_ATTN_MIX_COMB,
    TT_ATTN_IN, TT_Q, TT_KV, TT_CIDX, TT_ATTN_O, TT_ATTN_OA, TT_ATTN_OUT,
    TT_STREAMS_ATTN, TT_FFN_MIX_PRE, TT_FFN_IN, TT_ROUTE_LOGITS, TT_ROUTE_IDS,
    TT_ROUTE_PROB, TT_SHARED_DOWN, TT_FFN_OUT, TT_STREAMS_FFN, TT_FINAL_N, TT_LOGITS,
    TT_PUB_CKV, TT_PUB_IK,
};
inline const char *trace_tag_name(int t) {
    static const char *n[] = {"?", "embed", "engram", "attn_mix_pre", "attn_mix_post",
        "attn_mix_comb", "attn_in", "q", "kv", "cidx", "attn_o", "attn_oa", "attn_out",
        "streams_attn", "ffn_mix_pre", "ffn_in", "route_logits", "route_ids", "route_prob",
        "shared_down", "ffn_out", "streams_ffn", "final_n", "logits", "pub_ckv", "pub_ik"};
    return t > 0 && t <= TT_PUB_IK ? n[t] : "?";
}
