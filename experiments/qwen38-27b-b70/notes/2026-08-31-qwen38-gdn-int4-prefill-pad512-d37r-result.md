# Qwen3.8 packaged GDN pad D37r result

D37r is a valid negative package gate. The non-invasive wrapper supplied the
same hidden input hash to the packaged production forward in four fresh
processes, but received four different output hashes. The first generated
token difference remained at index 60.

Thus the packaged BA/output pad is active but insufficient for the true active
editable vLLM path. Earlier stage hooks reconstructed a different seven-argument
GDN core call, whereas active source head `ac7509e2b` calls the XPU core with
five arguments. D38 mirrors that exact active forward, including the packaged
helpers, and hashes QKVZ, padded BA, five-argument core, norm, and padded output
to locate the remaining source without making a package claim.
