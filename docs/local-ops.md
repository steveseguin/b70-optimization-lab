# Local Operations

This page records host-local operational pointers that are useful during driver,
runtime, service, and benchmark work. It must never contain secret values.

## Privileged Commands

The local sudo password file is outside this repo:

```text
/home/steve/SUDOPASSWORD.txt
```

Use it only when privileged local operations are actually needed, such as
driver/runtime package checks, systemd service changes, or recovery from a
known device/runtime failure. Never print the file contents, paste them into a
note, or commit a copy.

The repo `.gitignore` and user global Git ignore both exclude
`SUDOPASSWORD.txt`, `*.password.txt`, and common sudo-password variants. If a
new helper creates another credential filename, add that filename to both ignore
lists before using it.

## Delegating To Codex From Claude/OpenCode

When Claude or OpenCode is orchestrating work, prefer delegating concrete
research, audit, patch, and validation tasks to Codex/GPT through the CLI. GPT
token use is much less constrained on this host, so Claude/OpenCode should act
as manager/reviewer and let Codex handle bulky searches, source reading, and
iteration-heavy implementation where practical.

Useful Codex CLI forms:

```bash
codex --cd /home/steve/llm-optimizations
codex exec --cd /home/steve/llm-optimizations "audit the Qwen docs and propose focused cleanup"
codex review --cd /home/steve/llm-optimizations
codex resume --last
```

Keep tasks bounded: provide the target repo, files or lane, expected output, and
what must not be touched. For active experiments, explicitly say whether Codex
may stage, commit, push, or only report findings.

## B70 xe recovery policy

Do not reboot automatically and do not treat every stalled process as a device
wedge.

There is no one-experiment or one-model-load-per-boot rule. A boot ID is
provenance, never an admission or consumption token. After a run tears down,
later work may proceed on the same boot when it has an unused evidence path,
holds the required exclusive host/device locks, finds no conflicting process
or listener, revalidates exact source/runtime identity and storage/memory
floors, and passes the applicable bounded four-card health preflight. Every
device run must route success and failure through cleanup plus host, four-card,
and bounded journal postflight. A failed postflight blocks later device work
until health is re-established; it does not by itself mandate a reboot. Reboot
remains the last-resort recovery action described below.

1. Stop new launches. Preserve the failing run directory and first capture
   passive process, listener, progress, and journal evidence. Do not start an
   XPU-SMI or compute-probe loop on a possibly flapping card.
2. After clients are stopped, allow at least a 60-second bounded quiet period
   when work may still drain. Recheck passive progress and ownership evidence;
   do not create a retry storm on a possibly unhealthy driver.
3. Request graceful workload shutdown. If workers are blocked in the runtime
   and cannot exit after the chosen bound, preserve that fact before targeted
   termination. Only after assessing the risk, use at most one bounded active
   discovery/health probe if it is needed to classify the failure. The existing
   `scripts/qwen36-xpu-recovery-snapshot.sh` is not passive: even without
   `--copy-smoke` it makes many XPU-SMI calls across all four cards. Never use
   it as a polling loop during a suspected wedge.
4. If the bounded evidence shows a real device-wide/GuC wedge, verify that no
   process holds the render nodes, the console is still on the `ast` adapter,
   and no display manager uses xe. Also verify the booted kernel command line
   retains `xe.disable_display=1`. Then the locally proven recovery is to
   unbind all four B70s and reload xe. Re-resolve the live BDFs before use
   rather than assuming the currently recorded topology below:

   ```bash
   for bdf in 0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0; do
     echo "$bdf" | sudo tee /sys/bus/pci/drivers/xe/unbind >/dev/null
   done
   sudo modprobe -r xe
   sudo modprobe xe
   ```
5. After reload, require four-device discovery, expected BDF/UUID mapping,
   idle VRAM, a small per-card copy/compute smoke, a peer-access check, a
   representative XCCL/collective check, a known-good generation canary, and a
   clean new journal window before model work.

Do not use PCI FLR on this stack; prior FLR attempts wedged xe/Level Zero. A
host reboot is the last resort after evidence capture and failure of the less-
disruptive path, and requires explicit user authorization. Recovery never
converts the failed attempt into a valid measurement; start a fresh run with a
new identity.

Detailed local evidence is in
`experiments/laguna-s-2.1-xpu-b70/notes/2026-08-04-guc-firmware-wedge-root-cause.md`
and
`experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-topology-explosion-wedged-the-collective-stack.md`.

## Codex Subagents

Codex should use subagents whenever reasonable and available, especially for
parallel source audits, independent review of risky changes, log/result
classification, and research synthesis. The main Codex agent remains
responsible for final decisions, edits, verification, and not disturbing active
experiment processes.

## Local Model Storage

Primary hot-path model cache is still on the internal NVMe:

```text
/mnt/fast-ai/llm-cache/hf
```

As of 2026-07-03, an external 4 TB USB drive is available for overflow model
storage and archived benchmark artifacts:

```text
/mnt/usb-models
```

Device identity observed at setup and revalidated on 2026-08-08:

- block device: `/dev/sda2`;
- filesystem: NTFS (normally mounted through `ntfs-3g`, reported as
  `fuseblk`; kernel `ntfs3` was used only for the read-only recovery mount);
- label: `CorsairExternal`;
- mount path: `/mnt/usb-models`;
- created folders:
  - `/mnt/usb-models/llm-cache/hf`;
  - `/mnt/usb-models/bench-results`;
  - `/mnt/usb-models/models`.

The volume does not auto-mount. On 2026-08-08, apparent missing models were an
unmounted-drive symptom, followed by an NTFS `$MFT`/`$MFTMirr` mismatch. The
tree was inventoried read-only before repair, SMART reported no media errors,
and `ntfsfix` restored read/write mounting. See
[`reference-lab-storage.md`](reference-lab-storage.md) and the drive-local
`.storage-health/README.md` before filesystem maintenance. A Windows
`chkdsk /f` plus two reboots remains required at the next safe maintenance
window.

Use the internal NVMe cache for active benchmark hot paths unless disk pressure
or model count makes that impractical. Use the USB drive for alternate model
variants, overflow downloads, and archived large artifacts. Do not commit model
weights, USB paths full of artifacts, or generated cache contents to Git; record
only the model identity, local path, checksum if useful, and result summaries.
Use `/mnt/usb-models/llm-cache/hf` as `HF_HOME` for new large Hugging Face
downloads and `/mnt/usb-models/models/<model-family>/` for pinned standalone
GGUFs. Preserve the older `/mnt/usb-models/hf-cache` until it has been audited;
do not combine the two cache trees mechanically.

For Laguna S 2.1, the stricter policy established on 2026-07-23 overrides the
general overflow rule: the external Corsair `ntfs3` volume is backup-only.
Laguna model reads, caches, temporary files, logs, run roots, and recovery
evidence must stay on the internal NVMe/ext4 filesystem and fail closed rather
than falling back to `/media/steve/CorsairExternal`. The active model root is
`/mnt/fast-ai/llm-models/laguna-s-2.1`; the active artifact root is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1`. Frozen historical
evidence may retain its original USB path in notes and manifests.
