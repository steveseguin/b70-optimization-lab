"""Parking policy for runtime session checkpoints (SESSION-SWAP-DESIGN.md §9): which sessions to park, when,
and eviction. ctxkeeper owns this policy; the runtime owns save/inspect/restore/delete and every compatibility
check. This module never writes checkpoint internals: it addresses checkpoints by id and consumes `inspect`.

Three rules the contract fixes and this policy enforces before a device is touched:

1. A checkpoint is valid for one exact token prefix. The id of a parked session is the sha256 of that prefix's
   token ids, never a hash of the JSON messages (CONVERSATIONS.md): messages are rendered with the pinned chat
   template and tokenized with the pinned tokenizer first (`render` and `tokenize` are injected; the parity
   harness in experiments/own-xpu-runtime/integration/ is the evidence that they reproduce the engine's ids).
2. Continue = append. A new request restores only when the saved prefix is, token for token, a prefix of the
   new rendered prompt; the rest is the appended delta. Anything else (a notes cut or edit inside the saved
   prefix, a different model or engine identity, a shorter prompt) re-prefills, and the stale checkpoint goes.
3. Parking is bounded. Reserve a trusted new-checkpoint peak before SAVE, retaining the old checkpoint
   until the new one is visible. Conservative reservations include metadata/tokens/staging and detached
   in-use or ambiguous states. LRU eviction never assumes an in-use checkpoint was deleted.

The engine behind `Engine` is a stand-in until the runtime's request front exists; `FakeEngine` below models
the contract's fail-closed semantics for the tests. ctxkeeper does not call this module from its request path
yet (CHECKPOINT-INTEGRATION.md boundary).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

Render = Callable[[list[dict[str, Any]]], str]
Tokenize = Callable[[str], list[int]]


def prefix_hash(tokens: list[int]) -> str:
    return hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()


class Engine(Protocol):
    """The four operations of SESSION-SWAP-DESIGN.md §3 plus the running engine's own identity, as a proxy
    would reach them through the runtime's request front."""

    def identity(self) -> dict[str, str]: ...                                    # {"model": sha, "engine": sha}
    def save(self, checkpoint_id: str, tokens: list[int]) -> dict[str, Any]: ...   # -> manifest (visible)
    def inspect(self, checkpoint_id: str) -> dict[str, Any] | None: ...          # manifest, no device
    def restore(self, checkpoint_id: str, tokens: list[int]) -> dict[str, Any]: ...  # fail-closed; append delta
    def delete(self, checkpoint_id: str) -> str: ...                             # "ok" | "in_use" | "missing"

    # Optional at runtime when Parking has an explicit save_reservation_bytes.
    # Conservative NEW-checkpoint peak, including metadata, token files and staging;
    # existing checkpoints are counted separately. This operation must not SAVE.
    def save_size_bound(self, checkpoint_id: str, tokens: list[int]) -> int: ...


@dataclass
class Decision:
    action: str                      # "restore" (then append the delta) | "prefill"
    reason: str
    checkpoint_id: str | None = None
    saved_tokens: int = 0
    delta_tokens: int = 0
    total_tokens: int = 0
    dropped: str | None = None       # a stale checkpoint deleted on the way, or "kept: in_use"


@dataclass
class Parked:
    checkpoint_id: str
    tokens: int
    bytes: int
    last_used: float
    manifest: dict[str, Any] = field(default_factory=dict)


class Parking:
    """Policy only, called under the adapter's serialized owner mutex.

    accepted_contracts=None preserves the legacy label policy. An explicit immutable copy
    of exact (label, contract) pairs replaces that policy; engine/model identities still match.
    A trusted engine.save_size_bound(id, tokens) supplies conservative additional peak bytes;
    save_reservation_bytes is an optional fallback for engines without that method. Without
    either bound, park returns None before SAVE. A normal None requires the future adapter to
    RELEASE its pending reply. An exception is ambiguous: no retry, and its reservation stays
    charged until an explicit successful delete or proven-missing result reconciles it.
    """
    def __init__(self, engine: Engine, render: Render, tokenize: Tokenize, *, budget_bytes: int,
                 clock: Callable[[], float] = time.monotonic, log: Callable[[dict[str, Any]], None] | None = None,
                 accepted_contracts: set[tuple[str, str]] | None = None,
                 save_reservation_bytes: int | None = None) -> None:
        if type(budget_bytes) is not int or budget_bytes < 0:
            raise ValueError("budget_bytes must be a nonnegative integer")
        if save_reservation_bytes is not None and (type(save_reservation_bytes) is not int or save_reservation_bytes <= 0):
            raise ValueError("save_reservation_bytes must be a positive integer")
        if accepted_contracts is not None and any(not isinstance(pair, tuple) or len(pair) != 2 or
                any(not isinstance(value, str) or not value for value in pair) for pair in accepted_contracts):
            raise ValueError("accepted_contracts requires exact (label, contract) pairs")
        self.engine, self.render, self.tokenize = engine, render, tokenize
        self.budget_bytes, self.clock = budget_bytes, clock
        self.accepted_contracts = None if accepted_contracts is None else frozenset(accepted_contracts)
        self.save_reservation_bytes = save_reservation_bytes
        self.log = log or (lambda record: None)
        self.parked: dict[str, Parked] = {}      # session key -> its one checkpoint
        self.pending_delete: set[str] = set()    # checkpoint ids the runtime reported in_use
        self.retained_bytes: dict[str, int] = {}  # detached/in_use or ambiguous SAVE, still charged

    # -- the token prefix a request stands for -------------------------------------------------------------
    def prefix(self, view: list[dict[str, Any]]) -> list[int]:
        """The exact token prefix of a request: the view ctxkeeper would send, rendered and tokenized."""
        return self.tokenize(self.render(view))

    def checkpoint_id(self, session: str, tokens: list[int]) -> str:
        if (not isinstance(session, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,38}", session, re.ASCII) is None
                or session.endswith(".lock")):
            raise ValueError("session must be a safe native ID component of at most 39 ASCII characters")
        cid = f"{session}-{prefix_hash(tokens)[:24]}"
        if len(cid) > 64 or cid.endswith(".lock"):
            raise ValueError("checkpoint ID exceeds native admission")
        return cid

    # -- before a request: restore and append, or re-prefill -----------------------------------------------
    def compatible(self, manifest: dict[str, Any]) -> str | None:
        """The named check a manifest fails against the running engine, or None. Mirrors §4 for what a proxy
        can see; the runtime repeats every check itself at restore."""
        mine = self.engine.identity()
        model = manifest.get("model", {}).get("identity_tsv_sha256")
        if model != mine["model"]:
            return "model identity"
        if manifest.get("engine", {}).get("binary_sha256") != mine["engine"]:
            return "engine identity"
        if self.accepted_contracts is not None:
            if (manifest.get("label"), manifest.get("contract")) not in self.accepted_contracts:
                return "label/contract"
        elif manifest.get("label") not in ("experimental", "qualified-one-card"):
            return "label"
        return None

    @staticmethod
    def manifest_bytes(manifest: dict[str, Any]) -> int:
        sizes = [manifest["storage_bytes"]] if "storage_bytes" in manifest else [b["bytes"] for b in manifest["blobs"]]
        if any(type(size) is not int or size < 0 for size in sizes):
            raise ValueError("checkpoint byte counts must be nonnegative integers")
        return sum(sizes)

    def before_request(self, session: str, view: list[dict[str, Any]]) -> Decision:
        tokens = self.prefix(view)
        p = self.parked.get(session)
        if p is None:
            return Decision("prefill", "no checkpoint for this session", total_tokens=len(tokens))
        manifest = self.engine.inspect(p.checkpoint_id)
        if manifest is None:
            del self.parked[session]
            self.retained_bytes.pop(p.checkpoint_id, None)
            self.pending_delete.discard(p.checkpoint_id)
            return Decision("prefill", "checkpoint gone", total_tokens=len(tokens))
        p.bytes = max(p.bytes, self.manifest_bytes(manifest))
        failed = self.compatible(manifest)
        if failed is not None:
            return self.drop(session, tokens, f"{failed} differs from the running engine")
        state = manifest["token_state"]
        n = int(state["length"])
        if n > len(tokens) or prefix_hash(tokens[:n]) != state["tokens_sha256"]:
            return self.drop(session, tokens, "the saved prefix is not a prefix of this request (a cut or edit inside it, or a shorter prompt)")
        p.last_used = self.clock()
        d = Decision("restore", "the request extends the saved prefix exactly", p.checkpoint_id, n, len(tokens) - n, len(tokens))
        self.log({"event": "checkpoint restore planned", "session": session, "checkpoint": p.checkpoint_id, "saved": n, "delta": d.delta_tokens})
        return d

    def drop(self, session: str, tokens: list[int], why: str) -> Decision:
        p = self.parked.pop(session)
        status = self.delete(p.checkpoint_id, known_bytes=p.bytes)
        self.log({"event": "checkpoint dropped", "session": session, "checkpoint": p.checkpoint_id, "why": why, "delete": status})
        return Decision("prefill", why, total_tokens=len(tokens), dropped=p.checkpoint_id if status == "ok" else f"kept: {status}")

    def delete(self, checkpoint_id: str, *, known_bytes: int | None = None) -> str:
        if known_bytes is None:
            known_bytes = max([self.retained_bytes.get(checkpoint_id, 0),
                               *[p.bytes for p in self.parked.values() if p.checkpoint_id == checkpoint_id]])
            if not known_bytes:
                manifest = self.engine.inspect(checkpoint_id)
                if manifest is not None:
                    known_bytes = self.manifest_bytes(manifest)
        if known_bytes is not None:
            self.retained_bytes[checkpoint_id] = max(known_bytes, self.retained_bytes.get(checkpoint_id, 0))
        status = self.engine.delete(checkpoint_id)
        if status not in ("ok", "in_use", "missing"):
            raise ValueError("unrecognized checkpoint delete status")
        if status == "in_use":
            self.pending_delete.add(checkpoint_id)
        else:
            self.pending_delete.discard(checkpoint_id)
            self.retained_bytes.pop(checkpoint_id, None)
        return status

    # -- parking: one checkpoint per session, bounded in total ------------------------------------------------
    def park(self, session: str, view: list[dict[str, Any]], reply_tokens: list[int] = ()) -> Parked | None:
        """Reserve peak bytes before SAVE; return None if bounded parking cannot be admitted.
        Keep the session's old checkpoint until the new one is visible. An adapter must RELEASE
        the pending reply on no-save; there is no automatic live proxy wiring here.

        The saved prefix is what the engine holds: the request's rendered prompt ids followed by the ids it
        generated (`reply_tokens`), not a re-rendering of the conversation. The next request restores only if
        its rendered prompt extends that sequence exactly, which holds when the template renders the stored
        reply the way the engine produced it (opener, text, end token) and re-tokenizing the reply text gives
        the generated ids back. Whether it does for the pinned template and tokenizer is step 3 of the parity
        harness; a mismatch shows up here as a prefill with the "not a prefix" reason, never as a wrong restore."""
        tokens = self.prefix(view) + list(reply_tokens)
        cid = self.checkpoint_id(session, tokens)
        old = self.parked.get(session)
        if old is not None and old.checkpoint_id == cid:
            manifest = self.engine.inspect(cid)
            if manifest is not None:
                old.bytes = max(old.bytes, self.manifest_bytes(manifest))
                state = manifest.get("token_state", {})
                valid = self.compatible(manifest) is None and type(state.get("length")) is int and \
                    state["length"] == len(tokens) and state.get("tokens_sha256") == prefix_hash(tokens)
                if valid:
                    old.manifest, old.last_used = manifest, self.clock()
                    self.evict(keep=session)
                    return old if self.total_bytes() <= self.budget_bytes else None
                self.drop(session, tokens, "same-ID checkpoint no longer valid")
                return None  # No same-ID overwrite after detecting changed metadata.
            del self.parked[session]
            self.retained_bytes.pop(cid, None)
            self.pending_delete.discard(cid)
            old = None
        estimate = getattr(self.engine, "save_size_bound", None)
        bound = estimate(cid, tokens) if callable(estimate) else self.save_reservation_bytes
        if bound is None:
            self.log({"event": "parking refused", "session": session, "reason": "no SAVE peak-size admission"})
            return None
        if type(bound) is not int or bound <= 0:
            raise ValueError("SAVE peak-size bound must be a positive integer")
        if bound > self.budget_bytes or cid in self.retained_bytes:
            self.log({"event": "parking refused", "session": session, "reason": "oversized or unresolved checkpoint"})
            return None
        self.retry_deletes()
        self.evict(keep=session, target_bytes=self.budget_bytes - bound)
        if self.total_bytes() + bound > self.budget_bytes:
            self.log({"event": "parking refused", "session": session, "reason": "SAVE peak exceeds budget"})
            return None
        self.retained_bytes[cid] = bound  # Retain this charge if SAVE or its receipt is ambiguous.
        manifest = self.engine.save(cid, tokens)
        size = self.manifest_bytes(manifest)
        if size > bound:
            self.retained_bytes[cid] = size
            raise ValueError("engine exceeded admitted SAVE peak-size bound")
        self.parked[session] = Parked(cid, len(tokens), bound, self.clock(), manifest)
        self.retained_bytes.pop(cid)
        if old is not None:
            self.log({"event": "checkpoint replaced", "session": session, "old": old.checkpoint_id,
                      "delete": self.delete(old.checkpoint_id, known_bytes=old.bytes)})
        self.log({"event": "session parked", "session": session, "checkpoint": cid, "tokens": len(tokens), "bytes": bound})
        self.evict(keep=session)
        self.retry_deletes()
        return self.parked[session]

    def total_bytes(self) -> int:
        charged = dict(self.retained_bytes)
        for p in self.parked.values():
            charged[p.checkpoint_id] = max(p.bytes, charged.get(p.checkpoint_id, 0))
        return sum(charged.values())

    def evict(self, keep: str | None = None, *, target_bytes: int | None = None) -> list[str]:
        """Least recently used sessions go first until the parked bytes fit the budget; `keep` is never
        evicted; a checkpoint the runtime holds in use stays and is retried later."""
        gone: list[str] = []
        target = self.budget_bytes if target_bytes is None else target_bytes
        for session in sorted(self.parked, key=lambda k: self.parked[k].last_used):
            if self.total_bytes() <= target:
                break
            if session == keep:
                continue
            p = self.parked[session]
            status = self.engine.delete(p.checkpoint_id)   # not a drop: an in-use one stays tracked, no retry
            if status == "in_use":
                continue
            if status not in ("ok", "missing"):
                raise ValueError("unrecognized checkpoint delete status")
            self.retained_bytes.pop(p.checkpoint_id, None)
            self.pending_delete.discard(p.checkpoint_id)
            del self.parked[session]
            gone.append(session)
            self.log({"event": "checkpoint evicted", "session": session, "checkpoint": p.checkpoint_id, "bytes": p.bytes})
        return gone

    def retry_deletes(self) -> None:
        for cid in list(self.pending_delete):
            self.delete(cid)

    def status(self) -> dict[str, Any]:
        return {"sessions": {k: {"checkpoint": p.checkpoint_id, "tokens": p.tokens, "bytes": p.bytes} for k, p in self.parked.items()},
                "bytes": self.total_bytes(), "budget": self.budget_bytes, "pending_delete": sorted(self.pending_delete),
                "retained_bytes": dict(self.retained_bytes)}


class FakeEngine:
    """The contract's semantics without a device, for tests: save makes a visible manifest in the §6 shape;
    restore is fail-closed on identity and on exact prefix extension (v1.3 append); delete reports in_use while
    a restore holds the checkpoint."""

    def __init__(self, model: str = "model-a", engine: str = "engine-a", bytes_per_token: int = 28_400, floor: int = 56_600_000,
                 label: str = "qualified-one-card") -> None:
        self.model, self.engine, self.bpt, self.floor, self.label = model, engine, bytes_per_token, floor, label
        self.store: dict[str, dict[str, Any]] = {}
        self.in_use: set[str] = set()
        self.calls: list[tuple[str, str]] = []

    def identity(self) -> dict[str, str]:
        return {"model": self.model, "engine": self.engine}

    def save_size_bound(self, checkpoint_id: str, tokens: list[int]) -> int:
        return self.floor + self.bpt * len(tokens)  # Fake store has no filesystem/staging overhead.

    def save(self, checkpoint_id: str, tokens: list[int]) -> dict[str, Any]:
        self.calls.append(("save", checkpoint_id))
        m = {"format": "ownrt.session-checkpoint.v1", "label": self.label, "checkpoint_id": checkpoint_id,
             "model": {"identity_tsv_sha256": self.model}, "engine": {"binary_sha256": self.engine},
             "token_state": {"length": len(tokens), "position": len(tokens), "tokens_sha256": prefix_hash(tokens), "token_history": list(tokens)},
             "blobs": [{"name": "gdn.state", "bytes": self.floor}, {"name": "qsa.kv", "bytes": self.bpt * len(tokens)}]}
        self.store[checkpoint_id] = m
        return m

    def inspect(self, checkpoint_id: str) -> dict[str, Any] | None:
        self.calls.append(("inspect", checkpoint_id))
        return self.store.get(checkpoint_id)

    def restore(self, checkpoint_id: str, tokens: list[int]) -> dict[str, Any]:
        self.calls.append(("restore", checkpoint_id))
        m = self.store.get(checkpoint_id)
        if m is None:
            raise LookupError("no such checkpoint")
        if m["model"]["identity_tsv_sha256"] != self.model:
            raise ValueError("check failed: model identity")
        if m["engine"]["binary_sha256"] != self.engine:
            raise ValueError("check failed: engine identity")
        saved = m["token_state"]["token_history"]
        if tokens[:len(saved)] != saved:
            raise ValueError("check failed: prefix")
        self.in_use.add(checkpoint_id)
        return {"restored": len(saved), "appended": len(tokens) - len(saved)}

    def release(self, checkpoint_id: str) -> None:
        self.in_use.discard(checkpoint_id)

    def delete(self, checkpoint_id: str) -> str:
        self.calls.append(("delete", checkpoint_id))
        if checkpoint_id in self.in_use:
            return "in_use"
        return "ok" if self.store.pop(checkpoint_id, None) is not None else "missing"
