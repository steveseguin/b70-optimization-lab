FROM vllm/vllm-openai-xpu@sha256:c345345f9dcc751983a77cef128783513f2994fdd334e5cd382aeea36a2e0a36

# auto-round-kernel checks oneAPI support by executing `icpx --version`. The
# lean serving image carries torch 2.13 + libsycl.so.9 but omits that compiler
# frontend, causing a false pre-2026 result. Add a default-off diagnostic
# override without shadowing the real compiler command Triton also needs.
RUN sed -i 's/^import logging$/import logging\nimport os/' \
      /opt/venv/lib/python3.12/site-packages/auto_round_kernel/utils.py \
    && sed -i '/^def is_oneapi_ge_2026() -> bool:$/a\    if os.environ.get("AUTO_ROUND_XPU_ASSUME_ONEAPI_GE_2026") == "1":\n        return True' \
      /opt/venv/lib/python3.12/site-packages/auto_round_kernel/utils.py
