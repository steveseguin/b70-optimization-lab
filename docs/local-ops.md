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
