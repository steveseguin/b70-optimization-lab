# Contributor-reported source material

These files are preserved from `dominick253` PR #18. They are evidence of what
the contributor submitted, not maintainer-recommended commands.

`exact-contributor-launcher.sh` force-removes containers and runs a privileged,
host-networked, host-IPC container with seccomp disabled and automatic restart.
It is intentionally non-executable in the integrated tree. Use the hardened
launcher in the packet root for any future isolated test.

`evidence/` contains contributor-produced benchmark artifacts, model outputs,
and scripts. The original verifier is retained there unchanged, including its
use of Python assertions and the original benchmark monitor's fail-open journal
counter. Maintainer conclusions are recorded separately under `../validation/`.
