# ForgeCode v2.14.0 (Apache-2.0, tailcallhq/forgecode), tag commit 6ab58df3d8f11ce52c8d182359f4c76e74f29c0f. The
# static musl release binary from the GitHub release page, checked against the SHA-256 GitHub publishes for the asset
# (the official installer, https://forgecode.dev/cli, downloads this same asset). npm `forgecode` lags at 2.13.21.
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
ARG FORGE_URL=https://github.com/tailcallhq/forgecode/releases/download/v2.14.0/forge-x86_64-unknown-linux-musl
ARG FORGE_SHA=64832f828bf08961322e302243f352ee7c27e88d76f972574a3628c7b70cb1be
RUN python3 -I -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/forge')" "$FORGE_URL" \
 && echo "$FORGE_SHA  /tmp/forge" | sha256sum -c \
 && mkdir -p /opt/agent && install -m 755 /tmp/forge /opt/agent/forge && rm /tmp/forge

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/forgecode/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/forgecode/forge.toml /opt/agentbench/forge.toml
COPY agentbench/agents/forgecode/forge-agent.md /opt/agentbench/forge-agent.md
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=forgecode agentbench.agent.version="forgecode v2.14.0 (github tag commit 6ab58df3d8f11ce52c8d182359f4c76e74f29c0f) forge-x86_64-unknown-linux-musl sha256:64832f828bf08961322e302243f352ee7c27e88d76f972574a3628c7b70cb1be"
# FORGE_TRACKER=false stops only the system-info (git email) collection: 2.14.0 has no switch for its PostHog usage
# events or log shipping (crates/forge_tracker/src/dispatch.rs, can_track.rs); with --network none they cannot leave.
# SHELL: the shell tool runs $SHELL -c (default /bin/sh); bash is the agent user's login shell and gives the
# commands the task's BASH_ENV limits, as the other agents' bash tools do.
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost SHELL=/bin/bash FORGE_TRACKER=false
