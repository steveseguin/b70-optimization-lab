# OpenCode 1.19.0 (MIT, anomalyco/opencode). Only the linux-x64 platform package (a self-contained Bun binary) from the
# npm registry, installed by `npm ci` from the committed lockfile (integrity-checked), no install scripts. ripgrep
# from Debian, so OpenCode never downloads one.
ARG TASK_IMAGE
FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa AS install
WORKDIR /opt/pkg
COPY agentbench/agents/opencode/package.json agentbench/agents/opencode/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && mkdir -p /opt/agent \
 && cp node_modules/opencode-linux-x64/bin/opencode /opt/agent/opencode && chmod 755 /opt/agent/opencode \
 && sha256sum /opt/agent/opencode > /opt/agent/SHA256

FROM ${TASK_IMAGE}
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY sh -c \
    'apt-get update -qq && apt-get install -y -qq --no-install-recommends ripgrep=14.1.1-1+b4 && rm -rf /var/lib/apt/lists/*'
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/opencode/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/opencode/opencode.json /opt/agentbench/opencode.json
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=opencode agentbench.agent.version="opencode-linux-x64 1.19.0 (npm sha512-+UFxn2AbOqKEISBDqrWk5nHsZrPWBMVZ4H9R7tbnrt1+nYvEGejpg9tyt+QMrpBPYZP7F+D3Ym0vZbZcF7gSSw==; binary sha256 in /opt/agent/SHA256)"
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost SHELL=/bin/bash \
    OPENCODE_DISABLE_MODELS_FETCH=1 OPENCODE_DISABLE_AUTOUPDATE=1 OPENCODE_DISABLE_AUTOCOMPACT=1 \
    OPENCODE_DISABLE_PRUNE=1 OPENCODE_DISABLE_LSP_DOWNLOAD=1 OPENCODE_DISABLE_DEFAULT_PLUGINS=1 \
    OPENCODE_DISABLE_SHARE=1 OPENCODE_DISABLE_CLAUDE_CODE=1 OPENCODE_DISABLE_EXTERNAL_SKILLS=1
