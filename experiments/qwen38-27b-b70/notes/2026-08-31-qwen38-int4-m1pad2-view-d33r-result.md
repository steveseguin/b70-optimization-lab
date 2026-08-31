# Qwen3.8 INT4 M=1→2 view repair D33r result

D33r also failed the production boundary. The normalized layer-0 GDN
`out_proj` input was bit-identical in all four fresh processes, but the final
INT4 projection produced four different hashes.

Rebinding the result to the padded destination removed D33's post-matmul copy,
but it did not remove the race. The remaining padded-input allocation and copy
occur inside the custom C++ operator immediately before its asynchronous
oneDNN dispatch. That internal copy is not a dispatcher-visible producer of the
custom op's input and can race the consumer.

D34 therefore moves only the M=1→M=2 input construction to vLLM's Python
quantized-linear integration. The direct D32 test already proved that this
dispatcher-visible ordering produces one stable row-0 result.
