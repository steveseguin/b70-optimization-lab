# Qwen3.8 Gemma RMSNorm D3 receipt-format failure

Date: 2026-08-31

D3's four operator processes exited successfully, but vLLM wrote two warning
lines before each JSON payload. The aggregator correctly rejected the files as
non-JSON. This is a receipt-format failure: no D3 operator conclusion is
promoted from those artifacts.

D3b changes only receipt transport. The harness writes JSON directly to an
explicit mounted output file while stdout/stderr logs remain separate. It uses
a new result root and repeats all four fresh processes under a new
preregistration.
