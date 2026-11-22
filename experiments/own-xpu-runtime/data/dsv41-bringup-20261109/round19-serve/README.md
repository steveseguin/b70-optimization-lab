# round19-serve: the DeepSeek V4.1 Flash LAN server (2026-11-17 .. 11-22)

The engine as a server: tp134 added serve-1 (`OWN_SERVE=1`, requests on stdin, tokens on stdout, one conversation
kept). tp135 added reset-1 (a new conversation without a reload). The OpenAI-compatible server around it ran on the
reference host from 2026-11-17 at 1M context with guessing.

**The deployable version is its own repo now:**
[steveseguin/deepseek-v4.1-flash-b70](https://github.com/steveseguin/deepseek-v4.1-flash-b70). It holds:
- the engine source of tp135,
- the build, download and install scripts,
- the stable-mode host settings and the watchdog,
- the server and its tests,
- the plain-language notes on every optimization.

What is here:
- `chainq118.txt`: the lab log for the tp118 .. tp136 rounds, through the server, the freezes, and the watchdog.
- `t135-summary.txt`: the tp135 engine test after in-engine resets with the server's settings. Every answer is the
  same as the plain command-line reference, from 82 tokens to 194K.
- `http-20261122.txt`: the 12 web tests against the live server (ALL PASS, 2026-11-22).
- `scripts/`, the scripts as they ran on the reference host:
  - `server.py`, `config.json`, `preflight-serve.sh`, `t_http.py`: the server, its settings, its start checks and
    its web tests.
  - `run135.sh` and `run136k.sh`: the engine tests. `run136k.sh` (OWN_PREBUILD=0) froze the host, see below.
  - `memsample.sh`: the host-memory sampler.
  - `build135.sh`, `build136.sh`: the builds. `build137s.sh` was written and never run.

The rule that came out of this round: **load the model once per boot.** Every boot-time load passed (5 of 5). Every
test load started while the host was up froze it (3 of 3): `OWN_UP_PAR=2`, `OWN_UP_PAR=3` with `OWN_PREBUILD=0`,
and `OWN_PREBUILD=0` alone. The BMC hardware watchdog has been on since 2026-11-22, so a hung host resets itself.

The engine sources in this commit are the lab's newest, `267262e9db` (tp136 = tp135 + uppar-1, whose default of 6
is unchanged).
