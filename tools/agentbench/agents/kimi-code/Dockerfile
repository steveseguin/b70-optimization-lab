# Kimi Code 2.2.0 (MIT, MoonshotAI/kimi-code; npm @moonshot-ai/kimi-code, the successor of the archived kimi-cli).
# npm ci from the committed lockfile (every package checked against its registry integrity hash), no install scripts
# (the package's postinstall only migrates a legacy kimi-cli shim), no optional modules (node-pty is only loaded for
# interactive terminals and @mariozechner/clipboard only for image paste; print mode needs neither). Node 22 from the
# official image, pinned by digest (Kimi needs node >= 22.19).
ARG TASK_IMAGE
FROM node:22-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa AS install
WORKDIR /opt/agent
COPY agentbench/agents/kimi-code/package.json agentbench/agents/kimi-code/package-lock.json ./
RUN npm ci --omit=dev --omit=optional --ignore-scripts --no-audit --no-fund \
 && test "$(node -p 'require("./node_modules/@moonshot-ai/kimi-code/package.json").version')" = 2.2.0
# The one change to the release: the OpenAI SDK bundled in Kimi gives every Chat Completions request a fixed
# 10-minute total timeout (OpenAI.DEFAULT_TIMEOUT = 6e5; Kimi creates its client without a timeout option and no
# setting reaches it). Behind ctxkeeper the reply headers come only when the whole reply is done, so a reply that
# takes longer than 10 minutes would be cut off and re-sent. Raise that default to 1 hour; the check makes the build
# fail if the line is not there exactly once.
RUN f=node_modules/@moonshot-ai/kimi-code/dist/main.mjs \
 && test "$(grep -c '^[[:space:]]*OpenAI\.DEFAULT_TIMEOUT = 6e5;$' $f)" = 1 \
 && sed -i 's/^\([[:space:]]*\)OpenAI\.DEFAULT_TIMEOUT = 6e5;$/\1OpenAI.DEFAULT_TIMEOUT = 36e5;/' $f \
 && test "$(grep -c '^[[:space:]]*OpenAI\.DEFAULT_TIMEOUT = 36e5;$' $f)" = 1

FROM ${TASK_IMAGE}
COPY --from=install /usr/local/bin/node /usr/local/bin/node
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/kimi-code/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/kimi-code/config.toml agentbench/agents/kimi-code/tui.toml /opt/agentbench/kimi/
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=kimi-code agentbench.agent.version="@moonshot-ai/kimi-code 2.2.0 (npm sha512-I1w2l6JGYEUSwA1DTvYrw/kDJYjJQKHFON+RON61epDeTITvwpXoDn4Kgl4atA82RfwcsMp3KG6k8Yaoj6LT0A==; OpenAI SDK default timeout raised 600 s -> 3600 s)"
# KIMI_DISABLE_TELEMETRY: no telemetry or crash reports; KIMI_CODE_NO_AUTO_UPDATE: no update check or install;
# KIMI_CODE_LLM_HEADERS_TIMEOUT_MS: wait up to 1 hour for reply headers (the HTTP client's default is 300 s).
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    KIMI_DISABLE_TELEMETRY=1 KIMI_CODE_NO_AUTO_UPDATE=1 KIMI_CODE_LLM_HEADERS_TIMEOUT_MS=3600000
