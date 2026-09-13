#!/usr/bin/env python3
"""Render compose.yaml from the argv the real launcher would have handed to `docker run`.

The measured configuration lives in the recipe launchers, not in this package. Hand-copying 73
environment variables into a compose file is how a container packet silently stops matching the
result it claims. So the packet is generated: render-compose.sh runs the real launcher behind a
docker shim that captures argv instead of starting anything, and this script turns that argv into
compose services. Regenerate after any launcher change; tools/check-container-packet.py fails the
build when the committed file no longer matches what the launcher produces.

usage: render-container-compose.py ONE_GPU_ARGV TWO_GPU_ARGV OUT_YAML IMAGE_DIGEST_REF MODEL_DESC LAUNCHER GENERATOR
"""
from __future__ import annotations

import sys
from pathlib import Path


def read_argv(path: Path) -> list[str]:
    raw = path.read_bytes().split(b"\0")
    if raw and raw[-1] == b"":
        raw.pop()
    return [x.decode() for x in raw]


def split(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    """Return (env, serve_args).

    The serve arguments always begin with `--model /model`, so the image is the argument directly
    before the first `--model`. Anchoring on that avoids guessing which docker flags take values.
    """
    env: dict[str, str] = {}
    i = 1
    while i < len(argv):
        if argv[i] == "--env":
            k, _, v = argv[i + 1].partition("=")
            env[k] = v
            i += 2
        else:
            i += 1
    try:
        model_at = argv.index("--model")
    except ValueError:
        raise SystemExit("could not find --model in the captured argv")
    return env, argv[model_at:]


def yaml_scalar(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    # "-" marks a profile that this packet does not ship (a two-card-only result renders "two" alone).
    one_argv = read_argv(Path(sys.argv[1])) if sys.argv[1] != "-" else None
    two_argv = read_argv(Path(sys.argv[2])) if sys.argv[2] != "-" else None
    assert one_argv or two_argv, "at least one profile is required"
    out = Path(sys.argv[3])
    image = sys.argv[4]
    model_desc = sys.argv[5] if len(sys.argv) > 5 else "the verified model"
    launcher = sys.argv[6] if len(sys.argv) > 6 else "the recipe launcher"
    generator = sys.argv[7] if len(sys.argv) > 7 else "the packet's render-compose.sh"
    # Container names are operator-facing defaults, not part of the measured identity; keying them to
    # the served model name keeps already-published packets byte-identical when this is regenerated.
    served_prefix = sys.argv[8] if len(sys.argv) > 8 else out.parent.name
    depth = sys.argv[9] if len(sys.argv) > 9 else "3"

    profiles = []
    if one_argv:
        one_env, one_serve = split(one_argv); profiles.append(("one-gpu", one_env, one_serve, "one B70"))
    if two_argv:
        two_env, two_serve = split(two_argv); profiles.append(("two-gpu", two_env, two_serve, "two B70s"))
    envs = [e for _, e, _, _ in profiles]
    shared = {k: v for k, v in envs[0].items() if all(e.get(k) == v for e in envs)}
    per_profile = sorted(set().union(*(set(e) for e in envs)) - set(shared))
    one_env = envs[0]

    def serve_block(args: list[str], indent: str) -> str:
        return "\n".join(f"{indent}- {yaml_scalar(a)}" for a in args)

    def env_block(d: dict[str, str], keys, indent: str) -> str:
        return "\n".join(f"{indent}{k}: {yaml_scalar(d[k])}" for k in keys if k in d)

    lines = []
    lines.append("# GENERATED FILE - do not edit by hand.")
    lines.append(f"# Regenerate with: {generator}")
    lines.append(f"# Source of truth: {launcher}")
    lines.append("# CI check:        tools/check-container-packet.py")
    lines.append("")
    lines.append("x-b70-common: &b70-common")
    lines.append(f"  image: {image}")
    lines.append("  ulimits:")
    lines.append("    core: 0")
    lines.append("  mem_limit: 12g")
    lines.append("  memswap_limit: 20g")
    lines.append("  devices:")
    lines.append('    - "/dev/dri:/dev/dri"')
    lines.append("  group_add:")
    lines.append('    - "render"')
    lines.append("  cap_add:")
    lines.append("    - SYS_PTRACE")
    lines.append("  security_opt:")
    lines.append('    - "label=disable"')
    lines.append("  ipc: host")
    lines.append("  shm_size: 8gb")
    lines.append("  volumes:")
    lines.append(f'    - "${{MODEL_DIR:?set MODEL_DIR to the verified {model_desc} directory}}:/model:ro"')
    lines.append('    - "${VLLM_CACHE_DIR:-./cache}:/root/.cache/vllm"')
    lines.append("  healthcheck:")
    lines.append('    test: ["CMD", "python3", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen(\'http://127.0.0.1:8000/health\', timeout=5).status==200 else 1)"]')
    lines.append("    interval: 30s")
    lines.append("    timeout: 10s")
    lines.append("    retries: 40")
    lines.append("    start_period: 300s")
    lines.append("  environment:")
    lines.append(env_block(one_env, sorted(shared), "    "))
    lines.append("")
    lines.append("services:")
    for name, env, serve, cards in profiles:
        lines.append(f"  {name}:")
        lines.append("    <<: *b70-common")
        lines.append(f"    # {cards}; measured profile, MTP depth {depth} with the draft INT4 head and full decode-only graph capture.")
        lines.append(f"    container_name: ${{CONTAINER_NAME:-{served_prefix}-{name}}}")
        lines.append("    ports:")
        lines.append(f'      - "127.0.0.1:${{PORT:-18131}}:8000"')
        lines.append("    environment:")
        lines.append(env_block(one_env, sorted(shared), "      "))
        lines.append(env_block(env, sorted(per_profile), "      "))
        lines.append("    command:")
        lines.append(serve_block(serve, "      "))
        lines.append("")
    out.write_text("\n".join(lines).rstrip() + "\n")
    print(f"wrote {out} ({len(shared)} shared env, {len(per_profile)} per-profile env)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
