# Qwen Code 0.25.1 (Apache-2.0, QwenLM/qwen-code). npm ci from the committed lockfile (every package checked against
# its registry integrity hash), no install scripts, no optional native modules. Node 22 from the official image,
# pinned by digest.
ARG TASK_IMAGE
FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa AS install
WORKDIR /opt/agent
COPY agentbench/agents/qwen-code/package.json agentbench/agents/qwen-code/package-lock.json ./
RUN npm ci --omit=dev --omit=optional --ignore-scripts --no-audit --no-fund \
 && chmod +x node_modules/@qwen-code/qwen-code/vendor/ripgrep/x64-linux/rg

FROM ${TASK_IMAGE}
COPY --from=install /usr/local/bin/node /usr/local/bin/node
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/qwen-code/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/qwen-code/settings.json /opt/agentbench/qwen-settings.json
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=qwen-code agentbench.agent.version="@qwen-code/qwen-code 0.25.1 (npm sha512-6cEbtfx4Ugl1d3FdFLa8fcsG6knHuUUHqvDseLxGY06Xan8p7Fcd7+g5KlX694zX4mo/+Vh56AHxT/4R15zpYA==)"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    QWEN_CODE_MODELS_DEV=off QWEN_CODE_MODELS_DEV_REFRESH=off QWEN_USAGE_STATISTICS_ENABLED=false \
    QWEN_TELEMETRY_ENABLED=false QWEN_CODE_DISABLE_PRECONNECT=1 QWEN_DISABLE_AUTO_TITLE=1 \
    QWEN_STREAM_MAX_LIFETIME_MS=0 QWEN_STREAM_IDLE_TIMEOUT_MS=0 QWEN_CODE_DISABLE_CRON=1 \
    QWEN_CODE_SUPPRESS_YOLO_WARNING=1
