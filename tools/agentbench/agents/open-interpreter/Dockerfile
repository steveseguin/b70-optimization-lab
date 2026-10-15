# Open Interpreter rust-v0.0.56 (Apache-2.0, openinterpreter/openinterpreter, a fork of OpenAI Codex CLI), tag commit
# cc054cf52fa3585a3de50e0d4e0be6f9ee6677e8. The release package its official installer
# (https://www.openinterpreter.com/install) downloads for Linux x86_64: the static musl build from the GitHub release
# page, checked against the SHA-256 in the release's codex-package_SHA256SUMS (and GitHub's asset digest). Kept in
# the installer's layout (bin/, codex-path/rg, codex-resources/, codex-package.json); bin/i, a byte-identical copy of
# bin/interpreter installed as a short alias, is left out.
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
ARG OI_URL=https://github.com/openinterpreter/openinterpreter/releases/download/rust-v0.0.56/open-interpreter-package-x86_64-unknown-linux-musl.tar.gz
ARG OI_SHA=9e859353d6e2af28381489570d3ecf02060f7c73df5a652f3ca60c196835ccac
RUN python3 -I -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/oi.tar.gz')" "$OI_URL" \
 && echo "$OI_SHA  /tmp/oi.tar.gz" | sha256sum -c \
 && mkdir -p /opt/agent && tar -xzf /tmp/oi.tar.gz -C /opt/agent && rm /tmp/oi.tar.gz \
 && cmp /opt/agent/bin/i /opt/agent/bin/interpreter && rm /opt/agent/bin/i \
 && chmod -R a+rX /opt/agent && test -x /opt/agent/bin/interpreter

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/open-interpreter/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/open-interpreter/config.toml /opt/agentbench/oi-config.toml
COPY agentbench/agents/open-interpreter/model-catalog.json /opt/agentbench/oi-model-catalog.json
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=open-interpreter agentbench.agent.version="open-interpreter rust-v0.0.56 (github tag commit cc054cf52fa3585a3de50e0d4e0be6f9ee6677e8) open-interpreter-package-x86_64-unknown-linux-musl.tar.gz sha256:9e859353d6e2af28381489570d3ecf02060f7c73df5a652f3ca60c196835ccac"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
