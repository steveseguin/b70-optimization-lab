"""CPU-only conversion of a native TP1 checkpoint snapshot into a parking view.

This module neither runs the native tools nor reads a checkpoint directory. The
future request front must capture these bytes under the native shared lock and
must still run every native restore check before any upload. A successful plan
is an append decision, not authorization to restore unverified state blobs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import struct
from typing import Any, Mapping, Sequence


IDENTITY_FIELDS = (
    "model", "engine", "geometry", "dtypes", "tokenizer_identity",
    "label", "contract", "qualified_by",
)
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_CONTRACT_LABELS = {
    "v1.2+p181": "qualified-one-card",
    "v1.2+p198": "experimental-postreply-front",
}


class BridgeRefusal(ValueError):
    """A named refusal; callers must not treat malformed metadata as a hit."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise BridgeRefusal(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _int(value: Any, name: str, low: int, high: int) -> int:
    _require(type(value) is int and low <= value <= high, name)
    return value


def _json(data: bytes) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise BridgeRefusal("non-finite JSON value: " + value)

    _require(type(data) is bytes and len(data) <= 4 * 1024 * 1024, "JSON size/type")
    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BridgeRefusal("invalid JSON") from error
    _require(type(value) is dict, "JSON object required")
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def parking_prefix_hash(tokens: Sequence[int]) -> str:
    """ctxkeeper's policy hash, explicitly different from native tokens.bin."""
    return _sha(json.dumps(list(tokens), separators=(",", ":")).encode())


@dataclass(frozen=True)
class AppendPlan:
    checkpoint_id: str
    manifest_sha256: str
    input_tokens: tuple[int, ...]
    processed_tokens: int
    saved_history_tokens: int
    delta_tokens: int
    native_prefill_tokens: int  # pending token plus delta, not just delta
    max_new: int


@dataclass(frozen=True)
class CheckpointView:
    """Immutable bridge result; the native manifest is retained verbatim."""

    checkpoint_id: str
    manifest_sha256: str
    manifest_bytes: bytes
    processed_tokens: tuple[int, ...]
    pending_token: int
    context: int
    vocab: int
    native_inspect_mode: str

    @property
    def saved_history(self) -> tuple[int, ...]:
        return self.processed_tokens + (self.pending_token,)

    def parking_metadata(self) -> dict[str, Any]:
        """Policy-only projection, never a native manifest or restore input.

        Preserve real labels/identity/blob sizes, but express token_state as the
        full user-visible prefix expected by parking.Parking.before_request.
        No qualified label, binary identity or device evidence is invented.
        """
        native = _json(self.manifest_bytes)
        result = {k: native[k] for k in ("model", "engine", "label", "contract", "blobs")}
        result.update(
            format="ownrt.parking-checkpoint-view.v1",
            checkpoint_id=self.checkpoint_id,
            token_state={
                "length": len(self.saved_history),
                "tokens_sha256": parking_prefix_hash(self.saved_history),
            },
            bridge={
                "native_manifest_sha256": self.manifest_sha256,
                "native_token_state": native["token_state"],
                "native_inspect_mode": self.native_inspect_mode,
                "hash_encoding": "JSON integer array, compact separators, UTF-8",
                "full_state_revalidated_by_bridge": False,
            },
        )
        return result

    def plan_append(self, tokens: Sequence[int], *, max_new: int) -> AppendPlan:
        """Require H + [pending] + delta; never infer same-generation resume."""
        _require(isinstance(tokens, (list, tuple)), "input tokens must be a list or tuple")
        _require(len(tokens) <= self.context, "input exceeds context")
        request = tuple(_int(t, "input token outside vocabulary", 0, self.vocab - 1) for t in tokens)
        maximum = _int(max_new, "max_new outside native 1..512 bound", 1, 512)
        n = len(self.processed_tokens)
        _require(len(request) >= n + 1, "input omits pending token or shortens saved history")
        _require(request[:n] == self.processed_tokens, "processed prefix differs")
        _require(request[n] == self.pending_token, "pending token differs")
        _require(len(request) + maximum <= self.context, "append exceeds context")
        delta = len(request) - n - 1
        return AppendPlan(self.checkpoint_id, self.manifest_sha256, request, n, n + 1,
                          delta, delta + 1, maximum)


def validate_snapshot(
    inspect_stdout: bytes,
    *,
    inspect_returncode: int,
    manifest_bytes: bytes,
    tokens_bytes: bytes,
    next_token_bytes: bytes,
    checkpoint_id: str,
    expected_identity: Mapping[str, Any],
    admitted_contract: str = "v1.2+p181",
) -> CheckpointView:
    """Validate native inspect + exact small payloads; perform no I/O.

    expected_identity is supplied by the admitted running engine, not copied
    from an untrusted checkpoint. All IDENTITY_FIELDS must match exactly. This
    default remains packet181's TP1 contract. The experimental packet198
    contract requires explicit selection by the caller, with that admitted
    engine's complete expected identity. Selection neither qualifies the engine
    nor changes any label, binary check, or native manifest byte.
    """
    try:
        return _validate(inspect_stdout, inspect_returncode, manifest_bytes, tokens_bytes,
                         next_token_bytes, checkpoint_id, expected_identity, admitted_contract)
    except (KeyError, TypeError, OverflowError, struct.error) as error:
        raise BridgeRefusal("malformed checkpoint snapshot") from error


def _validate(stdout, returncode, manifest_bytes, tokens_bytes, next_token_bytes, checkpoint_id, expected, contract):
    _require(type(contract) is str and contract in _CONTRACT_LABELS, "unsupported admitted contract")
    _require(type(returncode) is int and returncode == 0, "native inspect failed")
    _require(type(checkpoint_id) is str and _ID.fullmatch(checkpoint_id) is not None
             and not checkpoint_id.endswith(".lock"),
             "invalid checkpoint id")
    inspected = _json(stdout)
    native = _json(manifest_bytes)
    _require(inspected["schema"] == "ownrt.checkpoint-inspect.v1", "inspect schema")
    _require(inspected["ok"] is True and inspected["error"] is None, "native inspect refused")
    _require(inspected["device_required"] is False, "unexpected device inspect")
    mode = inspected["mode"]
    _require(mode in ("metadata", "full"), "inspect mode")
    digest = _sha(manifest_bytes)
    _require(inspected["manifest_sha256"] == digest, "native manifest hash differs")
    _require(_canonical(inspected["manifest"]) == _canonical(native), "inspect manifest differs")
    _require(native["format"] == "ownrt.session-checkpoint.v1", "native manifest format")
    _require(native["checkpoint_id"] == inspected["checkpoint_id"] == checkpoint_id, "checkpoint id differs")
    for key in ("label", "contract"):
        _require(native[key] == inspected[key], "inspect " + key + " differs")
    _require(native["contract"] == contract and native["label"] == _CONTRACT_LABELS[contract],
             "unsupported checkpoint contract/label")
    _require(native["engine"]["profile"] == "tp1-full512", "unsupported profile")
    for key in IDENTITY_FIELDS:
        _require(_canonical(native[key]) == _canonical(expected[key]), key + " identity differs")
    for value in (native["engine"]["binary_sha256"], native["model"]["identity_tsv_sha256"]):
        _require(type(value) is str and _HEX.fullmatch(value) is not None, "production identity hash")
    _require(native["sampler"] == {"mode": "greedy-argmax", "state": None}, "unsupported sampler")
    _require("append" in native["operations"], "append is unsupported")
    verified = inspected["verified"]
    for key in ("manifest_seal", "fields_tsv_cross_check", "file_set_closed"):
        _require(verified[key] is True, "native inspect did not verify " + key)
    g, ts = native["geometry"], native["token_state"]
    context = _int(g["context"], "context", 1, 1 << 20)
    vocab = _int(g["vocab"], "vocabulary", 1, 1 << 31)
    eos = _int(g["eos"], "eos", 0, vocab - 1)
    n = _int(ts["length"], "processed length", 1, context - 1)
    _int(ts["position"], "position", n, n)
    _int(ts["prompt_length"], "prompt length", 1, n)
    pending = _int(ts["next_token"], "pending token outside vocabulary", 0, vocab - 1)
    _require(type(tokens_bytes) is bytes and len(tokens_bytes) == 4 * n, "tokens.bin extent")
    _require(_sha(tokens_bytes) == ts["tokens_sha256"], "tokens.bin hash differs")
    tokens = struct.unpack(f"<{n}i", tokens_bytes)
    for token in tokens:
        _int(token, "saved token outside vocabulary", 0, vocab - 1)
    history = [tokens[-2] if n > 1 else eos, tokens[-1]]
    _require(_canonical(ts["token_history"]) == _canonical(history), "native token_history differs")
    _require(type(next_token_bytes) is bytes and len(next_token_bytes) == 4, "next_token.bin extent")
    _require(struct.unpack("<i", next_token_bytes)[0] == pending, "pending token control differs")
    blobs = native["blobs"]
    _require(type(blobs) is list, "blob inventory")
    names, total, pending_blob = set(), 0, None
    for blob in blobs:
        name = blob["name"]
        _require(type(name) is str and name not in names, "duplicate/invalid blob name")
        names.add(name)
        total += _int(blob["bytes"], "blob bytes", 0, 1 << 40)
        if name == "next_token":
            pending_blob = blob
    _require(pending_blob is not None and pending_blob["bytes"] == 4
             and pending_blob["sha256"] == _sha(next_token_bytes), "pending token blob hash differs")
    _require(type(native["measurements"]["save_bytes"]) is int
             and native["measurements"]["save_bytes"] == total, "saved blob byte total differs")
    if mode == "metadata":
        for key in ("tokens", "semantic_blob_checks", "blobs_verified", "blob_bytes_verified"):
            _require(verified[key] is None, "metadata inspect overclaims " + key)
    else:
        _require(verified["tokens"] is True and verified["semantic_blob_checks"] is True,
                 "full inspect missing token/semantic checks")
        _int(verified["blobs_verified"], "full inspect blob count", len(blobs), len(blobs))
        _int(verified["blob_bytes_verified"], "full inspect byte count", total + 4 * n, total + 4 * n)
    return CheckpointView(checkpoint_id, digest, manifest_bytes, tokens, pending, context, vocab, mode)
