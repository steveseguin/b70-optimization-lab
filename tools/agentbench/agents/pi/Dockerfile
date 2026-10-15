# pi 1.2.0 (MIT, earendil-works/pi; npm @earendil-works/pi-coding-agent). npm ci from the committed lockfile (every
# package checked against its registry integrity hash), no install scripts, no optional modules (pi needs none: its
# image and sandbox helpers are WebAssembly). Node 22 from the official image, pinned by digest.
ARG TASK_IMAGE
FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa AS install
WORKDIR /opt/agent
COPY agentbench/agents/pi/package.json agentbench/agents/pi/package-lock.json ./
RUN npm ci --omit=dev --omit=optional --ignore-scripts --no-audit --no-fund \
 && test "$(node -p 'require("./node_modules/@earendil-works/pi-coding-agent/package.json").version')" = 1.2.0

FROM ${TASK_IMAGE}
COPY --from=install /usr/local/bin/node /usr/local/bin/node
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/pi/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/pi/models.json agentbench/agents/pi/settings.json /opt/agentbench/pi/
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=pi agentbench.agent.version="@earendil-works/pi-coding-agent 1.2.0 (npm sha512-h/4WaVWv1VlCaY8x8qEN5U+7jbF/e7+Ck6moPeEOFn5juMTWwNAXjwgYM7gRgbBYh8Zppwt6qWvJDzNTf4GNEQ==)"
# PI_OFFLINE: no model-catalog refresh, no startup network; PI_SKIP_VERSION_CHECK: no pi.dev version request;
# PI_TELEMETRY=0: no install/update report, no provider attribution headers.
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
