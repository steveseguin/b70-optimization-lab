# Control arm: the lab's own freeagent (tools/freeagent/freeagent.py, unmodified) in the same container shape as the
# third-party agents. A `docker` shim turns its `docker exec NAME bash -lc CMD` into a local `bash -lc CMD`.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY freeagent/freeagent.py /opt/agent/freeagent.py
COPY agentbench/agents/freeagent/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/freeagent/docker-shim /opt/agentbench/shim/docker
RUN sh /opt/agentbench/finalize.sh && sha256sum /opt/agent/freeagent.py > /opt/agent/VERSION
LABEL agentbench.agent=freeagent agentbench.agent.version="lab tools/freeagent/freeagent.py (sha256 in /opt/agent/VERSION)"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
