# Goose 1.54.0 (Apache-2.0, aaif-goose/goose, formerly block/goose). The static musl release build from the GitHub
# release page (no keyring, no self-update, no models.dev download in this build), checked against the SHA-256 that
# GitHub publishes for the asset.
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
RUN python3 -c "import urllib.request as u; u.urlretrieve('https://github.com/aaif-goose/goose/releases/download/v1.54.0/goose-x86_64-unknown-linux-musl.tar.gz', '/tmp/goose.tgz')" \
 && echo "777e49b6ae128fae06600f94bf51ff05c81572fce63c1581e9ea94bc49d64e42  /tmp/goose.tgz" | sha256sum -c \
 && mkdir -p /opt/agent && tar -xzf /tmp/goose.tgz -C /opt/agent && ls -la /opt/agent && test -x /opt/agent/goose

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/goose/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/goose/custom_provider.json /opt/agentbench/custom_provider.json
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=goose agentbench.agent.version="goose 1.54.0 goose-x86_64-unknown-linux-musl.tar.gz sha256:777e49b6ae128fae06600f94bf51ff05c81572fce63c1581e9ea94bc49d64e42"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    GOOSE_PATH_ROOT=/home/agent/goose GOOSE_PROVIDER=custom_ctxkeeper CTXKEEPER_API_KEY=sk-agentbench-dummy \
    GOOSE_MODE=auto GOOSE_CONTEXT_LIMIT=10000000 GOOSE_AUTO_COMPACT_THRESHOLD=0 GOOSE_TOOL_PAIR_SUMMARIZATION=false \
    GOOSE_MAX_TURNS=100000 GOOSE_DISABLE_SESSION_NAMING=true GOOSE_TELEMETRY_OFF=1 GOOSE_TELEMETRY_ENABLED=false \
    GOOSE_DISABLE_KEYRING=1
