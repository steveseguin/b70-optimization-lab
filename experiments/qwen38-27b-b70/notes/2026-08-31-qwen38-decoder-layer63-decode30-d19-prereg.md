# Qwen3.8 layer-63 decode-call-30 D19 preregistration

Date: 2026-08-31

Status: **preregistered before D19 model requests**

D18 found exact state through layer 31 on decode call 1. D14's invalid run first
branched at output 31, so call 30 is the latest established common-history
boundary. D19 hashes final decoder layer 63 after call 30 across four fresh
processes under all otherwise frozen conditions. Different output proves state
divergence has accumulated by call 30; exact output moves onset later.
Diagnostic only.
