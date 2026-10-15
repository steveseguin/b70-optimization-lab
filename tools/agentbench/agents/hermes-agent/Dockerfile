# Hermes Agent v0.22.1 (MIT, NousResearch/hermes-agent), tag commit 297552a9d646119871391d202509822cd86330df.
# PyPI stops at 0.19.0 (2026-07) and the project no longer builds wheels (setup.py refuses outside Nix), so this
# replicates its source install: the tag's source tarball from GitHub (SHA-256 checked) and its core dependencies
# from requirements.txt (hashes checked, wheels only, no install scripts). Hermes runs only on Python 3.14 (every
# core dependency is marked python_version >= '3.14'; uv.lock covers 3.14 only), so the venv uses the interpreter
# Hermes itself pins in pm/lock.json: python-build-standalone cpython 3.14.7+20260901 (SHA-256 from that lock),
# kept under /opt/agent-python, apart from the task's own Python 3.12.
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
ARG PY_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.14.7%2B20260901-x86_64-unknown-linux-gnu-install_only.tar.gz
ARG PY_SHA=0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0
ARG HERMES_URL=https://github.com/NousResearch/hermes-agent/archive/refs/tags/v0.22.1.tar.gz
ARG HERMES_SHA=45ebe864dbf65ecd31693a811ddd6e2e449b1878b835b563cf0a28d6a9c4bf38
RUN python3 -I -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/python.tar.gz'); urllib.request.urlretrieve(sys.argv[2], '/tmp/hermes.tar.gz')" "$PY_URL" "$HERMES_URL" \
 && echo "$PY_SHA  /tmp/python.tar.gz" | sha256sum -c \
 && echo "$HERMES_SHA  /tmp/hermes.tar.gz" | sha256sum -c \
 && mkdir -p /opt/agent-python /opt/hermes \
 && tar -xzf /tmp/python.tar.gz -C /opt/agent-python --strip-components=1 \
 && tar -xzf /tmp/hermes.tar.gz -C /opt/hermes --strip-components=1 \
 && rm -rf /tmp/*.tar.gz /opt/hermes/tests /opt/hermes/tests-js /opt/hermes/website /opt/hermes/apps \
           /opt/hermes/contributors /opt/hermes/evals /opt/hermes/.github
COPY agentbench/agents/hermes-agent/requirements.txt /tmp/requirements.txt
RUN /opt/agent-python/bin/python3.14 -m venv /opt/agent \
 && /opt/agent/bin/python -I -m pip install --no-deps --require-hashes --only-binary :all: --no-cache-dir \
      --disable-pip-version-check -r /tmp/requirements.txt \
 && echo /opt/hermes > /opt/agent/lib/python3.14/site-packages/hermes-source.pth \
 && /opt/agent/bin/python -I -m compileall -q -x '/(tests?|website|node_modules)/' /opt/hermes >/dev/null; \
    /opt/agent/bin/python -I -c "import hermes_cli, run_agent; print('hermes import ok')"

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent-python /opt/agent-python
COPY --from=install /opt/agent /opt/agent
COPY --from=install /opt/hermes /opt/hermes
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/hermes-agent/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/hermes-agent/config.yaml /opt/agentbench/hermes-config.yaml
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=hermes-agent agentbench.agent.version="hermes-agent v0.22.1 (github tag commit 297552a9d646119871391d202509822cd86330df, source tar.gz sha256 45ebe864dbf65ecd31693a811ddd6e2e449b1878b835b563cf0a28d6a9c4bf38; cpython 3.14.7+20260901 sha256 0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0)"
# Long-context replies can take many minutes and arrive in one SSE chunk: every request/stream/stale timer at 2 h,
# the gateway inactivity kill off. No on-demand installs (no network anyway).
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    HERMES_API_TIMEOUT=7200 HERMES_STREAM_READ_TIMEOUT=7200 HERMES_STREAM_STALE_TIMEOUT=7200 \
    HERMES_LOCAL_STREAM_STALE_TIMEOUT=7200 HERMES_API_CALL_STALE_TIMEOUT=7200 HERMES_AGENT_TIMEOUT=0 \
    HERMES_DISABLE_LAZY_INSTALLS=1 HERMES_YOLO_MODE=1
