# Closed build archival, 2026-10-17

Completed on `steve-b70s`, 18:07–18:17 UTC. **Packets 38 and 44 were archived and removed; packet45 was skipped.** The two removed trees occupied **6,554,791,936 bytes (6.10 GiB)**, with no hardlinks outside those trees. The roughly 12 GB target was not met because packet45 remains a live dependency.

| Build tree | Regular files | Archive bytes | Archive and restore record |
|---|---:|---:|---|
| `packet38-integrated/build` | 97,992 | 2,380,859,116 | [Verified archive](../packet38-integrated/build-ARCHIVED.md) |
| `packet44-context/build` | 115,423 | 1,439,389,433 | [Verified archive](../packet44-context/build-ARCHIVED.md) |

Read-only searches covered stage2 `packet4[6-9]*`, `packet5*`, `packet6*`, newly active `packet7*`, `screen/`, `ops/`, runtime `ops/`, and `/tmp/claude-1000/-home-steve/fn-run/*.sh`. Active packet/screen/chain/Codex units were inspected with `systemctl --user cat`. Symlinks throughout the runtime tree were resolved. Unprivileged `lsof -nP +D` found no open files in any candidate; supplementary accessible `/proc` descriptors/maps found no packet38/44 match. Other users' protected process records were inaccessible without sudo.

**Packet45 stays intact:** packet61x, packet64 and packet65 seals pin `packet45-merged3/build/fusion-rope.hpp`; `screen/v3-packet64-lanes/common.py` and packet64 `chain_seal.py`/`check_inputs.py` re-hash it at admission. Packet64 and packet61x also link `build/input` into packet45. These are runtime dependencies.

Packet38 census paths are historical provenance: `packet56-draft-prefix/memory_plan.py` validates embedded compressed evidence. Old `draft_baseline.py --prepare`/`import_captures.py` tools require restoration before reuse. Packet44 build references are historical `speed4_attribution.py` analyses; runtime references point to source outside `build/`. Neither removed tree had inbound symlinks or active/queued runtime readers identified.

Archives were written directly to `/mnt/raid-models/own-xpu-runtime-archive/` on `/dev/sdb2` (`fuseblk`), with no rename. Before each exact absolute-path `rm -rf --`, `tar -tzf` passed, regular-file counts matched `find -type f`, every member matched its original SHA-256, and two full archive checksum reads agreed. Hardlink entries resolve to verified archived bytes (36,864 in packet38; 49,920 in packet44). The initial packet38 verifier refused streaming hardlinks; it was corrected and the complete verification passed before any removal. Open-file and inventory checks were repeated immediately before removal.

All archive/check/removal work used `nice -n 19 ionice -c 3 taskset -c 8-15,24-31`. No GPU work, sudo, service changes, process kills, or power/memory/swap/page-cache changes. Only the two approved build trees were removed; notes and archives are the only new artifacts. Main was pulled with `git pull --rebase` before work.

`df -h /` before (18:07 UTC):

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p2  915G  855G   14G  99% /
```

After (18:17 UTC):

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p2  915G  850G   19G  98% /
```

Concurrent builds and runs also wrote to root, so the net filesystem change is smaller than the archived source allocation.
