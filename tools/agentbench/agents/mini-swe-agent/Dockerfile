# mini-swe-agent 2.4.6 (MIT, SWE-agent/mini-swe-agent). pip install of the full dependency closure, every wheel
# checked against the SHA-256 in requirements.txt (uv pip compile --generate-hashes), into a venv on the same Python
# image the task uses.
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
COPY agentbench/agents/mini-swe-agent/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/agent && /opt/agent/bin/pip install -q --no-deps --require-hashes --no-cache-dir -r /tmp/requirements.txt

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/mini-swe-agent/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/mini-swe-agent/overrides.yaml /opt/agentbench/overrides.yaml
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=mini-swe-agent agentbench.agent.version="mini-swe-agent 2.4.6 + litellm 1.105.1 (PyPI, hash-pinned closure in requirements.txt)"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    MSWEA_CONFIGURED=true MSWEA_SILENT_STARTUP=1 MSWEA_COST_TRACKING=ignore_errors \
    LITELLM_LOCAL_MODEL_COST_MAP=True LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS=True HF_HUB_OFFLINE=1
