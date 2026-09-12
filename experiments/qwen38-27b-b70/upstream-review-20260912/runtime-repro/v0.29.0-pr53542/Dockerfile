# Stock vLLM XPU v0.29.0 + the exact diff of open upstream PR #53542 (GDN metadata active runtime-K width), nothing else.
FROM vllm/vllm-openai-xpu:latest
COPY pr53542.gdn_attn_only.diff /tmp/pr53542.diff
RUN cd /opt/venv/lib/python3.12/site-packages && patch -p1 --dry-run --forward < /tmp/pr53542.diff && patch -p1 --forward < /tmp/pr53542.diff && python -m py_compile vllm/v1/attention/backends/gdn_attn.py && sha256sum vllm/v1/attention/backends/gdn_attn.py && rm /tmp/pr53542.diff
LABEL upstream.repro="v0.29.0+pr53542"
