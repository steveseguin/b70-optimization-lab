# Root disk cleanup, 2026-10-24

The SC117 LAN service needs root free space of at least 27 GB + 256 MiB at start and 27 GB + 128 MiB while it runs.
At 13:30 EDT, root had dropped to 113 MB above the running floor; Codex logs grow it down by about 35 MB per hour.
Two regenerable caches were removed. No evidence, build object or source was touched.

| Path | Size | Why it is safe |
|---|---:|---|
| `/tmp/claude-1000/-home-steve/1df77db8-…/scratchpad/sdvenv` | ~199 MB | Python virtualenv in an old Claude session scratchpad (pip packages only). |
| `~/.cache/ms-playwright/{chromium-1194,chromium_headless_shell-1194,ffmpeg-1011}` | ~925 MB | Playwright browser downloads, reinstalled on Oct 19 after the 10-18 cleanup classified them as reinstallable (`stage2/DISK-CLEANUP-20261018.md`). Reinstall with `npx playwright install` if a site preview needs it. |
