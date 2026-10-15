# Cline CLI 3.0.71 (Apache-2.0, cline/cline). Only the linux-x64 platform package (a self-contained Bun binary) from
# the npm registry, installed by `npm ci` from the committed lockfile (integrity-checked), no install scripts.
ARG TASK_IMAGE
FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa AS install
WORKDIR /opt/pkg
COPY agentbench/agents/cline/package.json agentbench/agents/cline/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && mkdir -p /opt/agent \
 && cp node_modules/@cline/cli-linux-x64/bin/cline /opt/agent/cline && chmod 755 /opt/agent/cline \
 && sha256sum /opt/agent/cline > /opt/agent/SHA256

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/cline/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/cline/providers.json agentbench/agents/cline/global-settings.json /opt/agentbench/
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=cline agentbench.agent.version="@cline/cli-linux-x64 3.0.71 (npm sha512-3bDa8a9KLAhj7UaoLYgXHl6wNpLp3t3REp37orGv9LMmGktqXw4z0wmHHgR7CApzwUVogaT93DowuW+vXvuEPw==; binary sha256 in /opt/agent/SHA256)"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    CLINE_DIR=/home/agent/.cline CLINE_DATA_DIR=/home/agent/.cline/data CLINE_NO_AUTO_UPDATE=1 IS_TEST=true \
    CLINE_SESSION_BACKEND_MODE=local BUN_CONFIG_HTTP_IDLE_TIMEOUT=0 \
    CLINE_MESSAGE_BUILDER_MAX_TOOL_RESULT_CHARS=1000000000 CLINE_MESSAGE_BUILDER_MIN_OUTDATED_REWRITE_BYTES=disable \
    CLINE_MESSAGE_BUILDER_MAX_TOTAL_TEXT_BYTES=1000000000000
