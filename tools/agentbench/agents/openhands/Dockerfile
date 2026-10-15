# OpenHands software-agent-sdk 1.54.0 (MIT, OpenHands/software-agent-sdk): openhands-sdk + openhands-tools from PyPI,
# the whole closure hash-pinned (requirements.txt), in a venv on the task's Python image; driven by oh_run.py.
# tmux from Debian: the SDK's terminal tool uses it when present (its subprocess fallback is marked less stable).
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
COPY agentbench/agents/openhands/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/agent && /opt/agent/bin/pip install -q --no-deps --require-hashes --no-cache-dir -r /tmp/requirements.txt

FROM ${TASK_IMAGE}
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY sh -c \
    'apt-get update -qq && apt-get install -y -qq --no-install-recommends tmux=3.5a-3 && rm -rf /var/lib/apt/lists/*'
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/openhands/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/openhands/oh_run.py /opt/agentbench/oh_run.py
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=openhands agentbench.agent.version="openhands-sdk 1.54.0 + openhands-tools 1.54.0 + litellm 1.105.1 (PyPI, hash-pinned closure in requirements.txt)"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    LITELLM_LOCAL_MODEL_COST_MAP=True LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS=True HF_HUB_OFFLINE=1 \
    OPENHANDS_SUPPRESS_BANNER=1 ANONYMIZED_TELEMETRY=false
