# Native RMS compiler candidate: CPU qualification

September14,2026. The native compiler screen02 failed exactness; this candidate
keeps original RMSNorm calls opaque before Inductor decomposition. It changes
one block-local FX graph and retains original parameters, epsilon, native RMS,
and compiler options. No global decomposition registry or active runtime was edited.

The actual tiny LTX block FX census observed15 RMS sites at both video token
counts64/256 (audio26):12 weighted eps1e-5 and3 unweighted eps1e-6. This is a
source/operator hypothesis, not proof that RMS was the native first divergence.

The initial CPU backend gate passed46 checks. Review added explicit canonical
fake/native output layout checks, nonfinite epsilon rejection and options copied
at backend construction. The hardened source passed51 checks, including BF16/F32
and widths32/2048/4096; three generated CPU wrappers retain two opaque calls each.
The original46-check source and evidence remain under data/native-rms-backend-cpu-01.
The final51-check evidence is under data/native-rms-backend-cpu-02.

The actual tiny BasicAVTransformerBlock compiled with unchanged options at both
stage token counts and seeds17/123. All four cases matched eager video/audio and
compiled repeats exactly. Two compiled graphs each contained15 native RMS sites;
independent generated-wrapper AST census confirmed15 opaque native calls in each.
Peak process RSS was1,079,620KiB. These fixtures use tiny32-wide CPU blocks, not
native4096/2048-wide GPU weights. No full-model correctness or speed is claimed.

Artifacts: scripts/ltx_native_rms_backend.py, scripts/census-ltx-rms-fx-cpu.py,
scripts/test-native-rms-backend-cpu.py, scripts/test-ltx-native-rms-block-cpu.py;
data/compiler-screen-02-rms-fx-census-cpu.json and data/native-rms-block-cpu-01.
Each data directory retains receipts and compressed textual source evidence.
External evidence root: /mnt/fast-ai/bench-results/ltx25-baseline-20260913.
Final backend SHA256:09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb.

Next: separate immutable packet04 and v3 campaign client, one controlled LTX
application replacement, then native stage/repeat and original four-output gates.
The decoder extent and loader-memory candidates remain separate and inactive.
An initial root check-only invocation used system Python without Torch metadata;
it exited before imports/ownership/device work. Correct-venv check-only passed.
