# Mistral Vibe 2.26.1 (Apache-2.0, mistralai/mistral-vibe; PyPI mistral-vibe). Every package (97, from requirements.txt
# made by `uv pip compile --generate-hashes`) is installed from PyPI as a wheel checked against its hash, without
# resolving anything further (--no-deps). The venv is built on the same Python image as the task image
# (python:3.12-slim, 3.12.15), so it runs unchanged there.
ARG TASK_IMAGE
FROM python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS install
COPY agentbench/agents/mistral-vibe/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/agent \
 && /opt/agent/bin/pip install --no-cache-dir --disable-pip-version-check --no-deps --require-hashes \
      --only-binary :all: -r /tmp/requirements.txt \
 && test "$(/opt/agent/bin/python -c 'import importlib.metadata as m; print(m.version("mistral-vibe"))')" = 2.26.1

FROM ${TASK_IMAGE}
COPY --from=install /opt/agent /opt/agent
COPY agentbench/bridge.py agentbench/common/entry.sh agentbench/common/finalize.sh /opt/agentbench/
COPY agentbench/agents/mistral-vibe/run.sh /opt/agentbench/run.sh
COPY agentbench/agents/mistral-vibe/config.toml /opt/agentbench/vibe-config.toml
RUN sh /opt/agentbench/finalize.sh
LABEL agentbench.agent=mistral-vibe agentbench.agent.version="mistral-vibe 2.26.1 (PyPI wheel mistral_vibe-2.26.1-cp312-abi3-manylinux_2_28_x86_64.whl sha256:1ceb43e38a2e82cb8c54e1032b011874f8422e998cf87b4a3fdf58704133de55)"
# VIBE_CLI=python: the Python CLI (programmatic mode), never the bundled Rust TUI. The other off switches are in
# config.toml (telemetry, which also gates the GrowthBook experiments; update checks; auto-update; connectors;
# subagents; titles). VIBE_TEST_DISABLE_AUTO_TITLE=1 is Vibe's own kill switch for background title calls.
ENV NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    VIBE_CLI=python VIBE_TEST_DISABLE_AUTO_TITLE=1
