#!/usr/bin/env python3
"""Run the fixed Flash-Next vision fixture v1 against a pinned endpoint."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA = "neural.download.fixed-vision-fixture.v1"
RESULT_SCHEMA = "neural.download.fixed-vision-result.v1"


class GateFailure(RuntimeError):
    """Raised when a frozen fixture or response gate fails."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def write_new(path: Path, payload: bytes) -> None:
    if path.exists():
        raise GateFailure(f"refusing to overwrite {path}")
    path.write_bytes(payload)


def load_generator(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("fixed_vision_fixture_v1", path)
    if spec is None or spec.loader is None:
        raise GateFailure(f"could not load fixture generator {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_repo_path(repo: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise GateFailure(f"{label} must be a nonempty repository-relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise GateFailure(f"{label} is not a safe repository-relative path: {value}")
    resolved = (repo / relative).resolve()
    if not resolved.is_relative_to(repo.resolve()):
        raise GateFailure(f"{label} escapes the repository: {value}")
    return resolved


def validate_manifest(
    manifest_path: Path,
    repo: Path,
) -> tuple[dict[str, Any], ModuleType, bytes, dict[str, Any]]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise GateFailure(f"manifest schema must be {SCHEMA}")

    fixture = manifest.get("fixture")
    protocol = manifest.get("protocol")
    cases = manifest.get("cases")
    tooling = manifest.get("tooling")
    if not isinstance(fixture, dict):
        raise GateFailure("manifest.fixture must be an object")
    if not isinstance(protocol, dict):
        raise GateFailure("manifest.protocol must be an object")
    if not isinstance(cases, list) or len(cases) != 3:
        raise GateFailure("manifest must contain exactly three grounded cases")
    if not isinstance(tooling, dict):
        raise GateFailure("manifest.tooling must be an object")

    generator_path = resolve_repo_path(
        repo, tooling.get("generator_path"), "tooling.generator_path"
    )
    client_path = resolve_repo_path(repo, tooling.get("client_path"), "tooling.client_path")
    if generator_path != (manifest_path.parent / "fixed_vision_fixture_v1.py").resolve():
        raise GateFailure("manifest does not point at its adjacent fixture generator")
    if client_path != Path(__file__).resolve():
        raise GateFailure("manifest client path is not this client")
    if sha256_path(generator_path) != tooling.get("generator_sha256"):
        raise GateFailure("fixture generator SHA-256 changed")
    if sha256_path(client_path) != tooling.get("client_sha256"):
        raise GateFailure("fixture client SHA-256 changed")

    generator = load_generator(generator_path)
    png = generator.build_png()
    generated_receipt = generator.fixture_receipt()
    expected_fixture_fields = {
        "fixture_id": fixture.get("fixture_id"),
        "mime_type": fixture.get("mime_type"),
        "width": fixture.get("width"),
        "height": fixture.get("height"),
        "color_mode": fixture.get("color_mode"),
        "byte_count": fixture.get("byte_count"),
        "sha256": fixture.get("sha256"),
    }
    if generated_receipt != expected_fixture_fields:
        raise GateFailure(
            "generated fixture receipt differs from manifest: "
            f"{generated_receipt!r} != {expected_fixture_fields!r}"
        )
    if sha256_bytes(png) != fixture.get("sha256"):
        raise GateFailure("generated fixture byte SHA-256 changed")
    if sha256_bytes(generator.build_rgb_pixels()) != fixture.get("rgb_sha256"):
        raise GateFailure("generated fixture RGB pixel SHA-256 changed")

    if protocol.get("endpoint_path") != "/v1/chat/completions":
        raise GateFailure("protocol endpoint path changed")
    if protocol.get("temperature") != 0 or protocol.get("top_p") != 1.0:
        raise GateFailure("protocol must retain deterministic sampling")
    if protocol.get("seed") != 20260828:
        raise GateFailure("protocol seed changed")
    if protocol.get("max_tokens") != 16:
        raise GateFailure("protocol max_tokens changed")
    if protocol.get("chat_template_kwargs") != {"enable_thinking": False}:
        raise GateFailure("protocol must disable thinking for exact short answers")
    if protocol.get("repetitions_per_case") != 3:
        raise GateFailure("protocol requires three repetitions per grounded case")
    if protocol.get("stop_on_first_failure") is not True:
        raise GateFailure("protocol must stop on the first failed gate")

    expected_cases = {
        "ocr_code": ("B7X9", "unique OCR/code"),
        "right_square_color": ("blue", "spatial/color"),
        "bottom_circle_count": ("3", "count"),
    }
    seen_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise GateFailure("each case must be an object")
        case_id = case.get("id")
        if case_id in seen_ids or case_id not in expected_cases:
            raise GateFailure(f"unexpected or duplicate case id: {case_id!r}")
        seen_ids.add(case_id)
        expected_answer, category = expected_cases[case_id]
        if case.get("expected_answer") != expected_answer:
            raise GateFailure(f"expected answer changed for {case_id}")
        if case.get("category") != category:
            raise GateFailure(f"category changed for {case_id}")
        if case.get("normalization") != "strip":
            raise GateFailure(f"normalization changed for {case_id}")
        if not isinstance(case.get("prompt"), str) or not case["prompt"]:
            raise GateFailure(f"prompt missing for {case_id}")
    if seen_ids != set(expected_cases):
        raise GateFailure("grounded case inventory is incomplete")

    static_receipt = {
        "schema": SCHEMA,
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "generator_path": str(generator_path),
        "generator_sha256": sha256_path(generator_path),
        "client_path": str(client_path),
        "client_sha256": sha256_path(client_path),
        "fixture": generated_receipt,
        "rgb_sha256": fixture["rgb_sha256"],
        "case_ids": [case["id"] for case in cases],
        "repetitions_per_case": protocol["repetitions_per_case"],
        "status": "passed",
    }
    return manifest, generator, png, static_receipt


def build_request_payload(
    model: str,
    case: dict[str, Any],
    protocol: dict[str, Any],
    png: bytes,
    mime_type: str,
) -> dict[str, Any]:
    data_url = f"data:{mime_type};base64,{base64.b64encode(png).decode('ascii')}"
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": case["prompt"]},
                ],
            }
        ],
        "chat_template_kwargs": protocol["chat_template_kwargs"],
        "temperature": protocol["temperature"],
        "top_p": protocol["top_p"],
        "seed": protocol["seed"],
        "max_tokens": protocol["max_tokens"],
        "stream": False,
    }


def post_request(
    url: str,
    body: bytes,
    request_id: str,
    timeout: int,
) -> tuple[int, bytes, dict[str, str]]:
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers.items())


def validate_response(
    parsed: object,
    status_code: int,
    model: str,
    expected_answer: str,
    expected_prompt_tokens: int,
    max_tokens: int,
) -> dict[str, Any]:
    if status_code != 200:
        raise GateFailure(f"HTTP status is {status_code}, expected 200")
    if not isinstance(parsed, dict):
        raise GateFailure("response must decode to an object")
    if parsed.get("model") != model:
        raise GateFailure(f"served model changed: {parsed.get('model')!r}")
    choices = parsed.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise GateFailure("response must contain exactly one choice")
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
        raise GateFailure("response must have finish_reason=stop")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise GateFailure("response choice has no message object")
    content = message.get("content")
    if not isinstance(content, str):
        raise GateFailure("response message content must be text")
    normalized = content.strip()
    if normalized != expected_answer:
        raise GateFailure(
            f"grounded answer mismatch: expected {expected_answer!r}, got {normalized!r}"
        )

    usage = parsed.get("usage")
    if not isinstance(usage, dict):
        raise GateFailure("response has no usage object")
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if prompt_tokens != expected_prompt_tokens:
        raise GateFailure(
            "prompt token count changed: "
            f"expected {expected_prompt_tokens}, got {prompt_tokens!r}"
        )
    if not isinstance(completion_tokens, int) or not 1 <= completion_tokens <= max_tokens:
        raise GateFailure("completion token count is outside the frozen bound")
    if total_tokens != prompt_tokens + completion_tokens:
        raise GateFailure("usage total does not equal prompt plus completion")
    prompt_details = usage.get("prompt_tokens_details")
    if not isinstance(prompt_details, dict):
        raise GateFailure("prompt_tokens_details is required")
    if prompt_details.get("cached_tokens") != 0:
        raise GateFailure("cached prompt tokens must be zero")
    if prompt_details.get("created_cache_tokens") != 0:
        raise GateFailure("created cache tokens must be zero")

    return {
        "content": content,
        "normalized": normalized,
        "normalized_sha256": sha256_bytes(normalized.encode("utf-8")),
        "finish_reason": choice["finish_reason"],
        "usage": usage,
        "usage_sha256": sha256_bytes(canonical_json_bytes(usage)),
        "prompt_tokens_details_sha256": sha256_bytes(
            canonical_json_bytes(prompt_details)
        ),
    }


def run_protocol(
    base_url: str,
    model: str,
    timeout: int,
    output_dir: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    png: bytes,
    static_receipt: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    if output_dir.exists():
        raise GateFailure(f"refusing to reuse output directory {output_dir}")
    output_dir.mkdir(parents=True)
    write_new(output_dir / "fixture.png", png)
    write_new(output_dir / "manifest-used.json", manifest_path.read_bytes())
    write_new(
        output_dir / "static-validation.json",
        json.dumps(static_receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    protocol = manifest["protocol"]
    endpoint = f"{base_url.rstrip('/')}{protocol['endpoint_path']}"
    results: list[dict[str, Any]] = []
    failed = False
    for case_index, case in enumerate(manifest["cases"]):
        payload = build_request_payload(
            model,
            case,
            protocol,
            png,
            manifest["fixture"]["mime_type"],
        )
        request_body = canonical_json_bytes(payload)
        request_sha256 = sha256_bytes(request_body)
        for repetition in range(1, protocol["repetitions_per_case"] + 1):
            request_id = (
                f"q38-fixed-vision-v1-{case_index:02d}-{case['id']}-r{repetition}"
            )
            prefix = f"{case_index:02d}-{case['id']}-r{repetition}"
            request_path = output_dir / f"{prefix}-request.json"
            response_path = output_dir / f"{prefix}-response.json"
            write_new(request_path, request_body)
            started = time.perf_counter()
            status_code: int | None = None
            raw_response = b""
            response_headers: dict[str, str] = {}
            gate: dict[str, Any] | None = None
            error_type: str | None = None
            error_message: str | None = None
            try:
                status_code, raw_response, response_headers = post_request(
                    endpoint, request_body, request_id, timeout
                )
                write_new(response_path, raw_response)
                parsed = json.loads(raw_response)
                gate = validate_response(
                    parsed,
                    status_code,
                    model,
                    case["expected_answer"],
                    manifest["artifact_processing_receipt"][
                        "thinking_disabled_prompt_token_counts_by_case"
                    ][case["id"]],
                    protocol["max_tokens"],
                )
            except Exception as error:  # Preserve every transport and gate failure.
                error_type = type(error).__name__
                error_message = str(error)
                if raw_response and not response_path.exists():
                    write_new(response_path, raw_response)
                failed = True
            elapsed_seconds = time.perf_counter() - started
            item = {
                "case_id": case["id"],
                "category": case["category"],
                "repetition": repetition,
                "request_id": request_id,
                "request_path": request_path.name,
                "request_sha256": request_sha256,
                "request_byte_count": len(request_body),
                "response_path": response_path.name if response_path.exists() else None,
                "response_sha256": sha256_bytes(raw_response) if raw_response else None,
                "response_byte_count": len(raw_response),
                "http_status": status_code,
                "response_content_type": response_headers.get("Content-Type"),
                "elapsed_seconds": elapsed_seconds,
                "expected_answer": case["expected_answer"],
                "gate": gate,
                "passed": gate is not None,
                "error_type": error_type,
                "error": error_message,
            }
            results.append(item)
            print(
                json.dumps(
                    {
                        "case_id": case["id"],
                        "repetition": repetition,
                        "passed": item["passed"],
                        "http_status": status_code,
                        "elapsed_seconds": round(elapsed_seconds, 3),
                        "normalized": gate["normalized"] if gate else None,
                        "error_type": error_type,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if failed and protocol["stop_on_first_failure"]:
                break
        if failed and protocol["stop_on_first_failure"]:
            break

    expected_result_count = len(manifest["cases"]) * protocol["repetitions_per_case"]
    repeat_groups: dict[str, dict[str, Any]] = {}
    for case in manifest["cases"]:
        matching = [item for item in results if item["case_id"] == case["id"]]
        repeat_groups[case["id"]] = {
            "observed": len(matching),
            "expected": protocol["repetitions_per_case"],
            "passed": len(matching) == protocol["repetitions_per_case"]
            and all(item["passed"] for item in matching),
            "unique_request_sha256": sorted(
                {item["request_sha256"] for item in matching}
            ),
            "unique_normalized_sha256": sorted(
                {
                    item["gate"]["normalized_sha256"]
                    for item in matching
                    if item["gate"] is not None
                }
            ),
            "unique_prompt_tokens": sorted(
                {
                    item["gate"]["usage"]["prompt_tokens"]
                    for item in matching
                    if item["gate"] is not None
                }
            ),
            "unique_usage_sha256": sorted(
                {
                    item["gate"]["usage_sha256"]
                    for item in matching
                    if item["gate"] is not None
                }
            ),
            "unique_prompt_tokens_details_sha256": sorted(
                {
                    item["gate"]["prompt_tokens_details_sha256"]
                    for item in matching
                    if item["gate"] is not None
                }
            ),
        }
        repeat_groups[case["id"]]["passed"] = (
            repeat_groups[case["id"]]["passed"]
            and len(repeat_groups[case["id"]]["unique_request_sha256"]) == 1
            and len(repeat_groups[case["id"]]["unique_normalized_sha256"]) == 1
            and len(repeat_groups[case["id"]]["unique_prompt_tokens"]) == 1
            and len(repeat_groups[case["id"]]["unique_usage_sha256"]) == 1
            and len(
                repeat_groups[case["id"]][
                    "unique_prompt_tokens_details_sha256"
                ]
            )
            == 1
        )

    passed = (
        len(results) == expected_result_count
        and all(item["passed"] for item in results)
        and all(group["passed"] for group in repeat_groups.values())
    )
    summary = {
        "schema": RESULT_SCHEMA,
        "status": "passed" if passed else "failed",
        "base_url": base_url.rstrip("/"),
        "endpoint": endpoint,
        "model": model,
        "manifest": static_receipt,
        "fixture_artifact": {
            "path": "fixture.png",
            "sha256": sha256_path(output_dir / "fixture.png"),
            "byte_count": len(png),
        },
        "protocol": protocol,
        "expected_result_count": expected_result_count,
        "observed_result_count": len(results),
        "results": results,
        "repeat_groups": repeat_groups,
        "credit_scope": manifest["credit_scope"],
    }
    summary_bytes = json.dumps(summary, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    write_new(output_dir / "result.json", summary_bytes)
    return (0 if passed else 1), summary


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    default_manifest = (
        repo
        / "experiments/qwen38-flash-next-fp8-b70/fixtures/"
        "fixed-vision-fixture-v1.json"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=default_manifest)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    manifest, _generator, png, static_receipt = validate_manifest(manifest_path, repo)
    if args.validate_only:
        print(json.dumps(static_receipt, indent=2, sort_keys=True))
        return 0
    if not args.base_url or not args.model or args.output_dir is None:
        parser.error("normal execution requires --base-url, --model, and --output-dir")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    rc, _summary = run_protocol(
        args.base_url,
        args.model,
        args.timeout,
        args.output_dir.resolve(),
        manifest_path,
        manifest,
        png,
        static_receipt,
    )
    return rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateFailure as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
