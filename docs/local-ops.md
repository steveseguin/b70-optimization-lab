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
- filesystem: `ntfs3`;
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
