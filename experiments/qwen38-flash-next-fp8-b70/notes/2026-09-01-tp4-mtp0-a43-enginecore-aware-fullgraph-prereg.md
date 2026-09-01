# Qwen3.8 Flash-Next FP8 A43 EngineCore-aware full-graph preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A43 is the fresh attempt-43/port-19715 successor. Relative to A42 it changes
only paths/identity and the hash-bound runtime verifier. Workers still require
the exact trace selector; EngineCore may omit it after consumption but may not
declare a different value. Four exact rank logs and the existing compile-target
allowlist remain mandatory. Model, official FP8 revision, TP4/EP4 MTP0,
full-decode graph, PLE, prompts, authorities, quality battery, and teardown are
unchanged. Any failure receives zero credit; a pass still needs trace-off
replication. No reboot or per-boot rule applies.
