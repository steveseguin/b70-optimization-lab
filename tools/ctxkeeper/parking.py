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
3. Parking is bounded. Each session holds at most one checkpoint; the total parked bytes (from `inspect`)
   stay under a budget by evicting the least recently used sessions; a checkpoint the runtime reports `in_use`
   is never deleted and is retried on the next pass.

The engine behind `Engine` is a stand-in until the runtime's request front exists; `FakeEngine` below models
the contract's fail-closed semantics for the tests. ctxkeeper does not call this module from its request path
yet (CHECKPOINT-INTEGRATION.md boundary).
"""
from __future__ import annotations

import hashlib
import json
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
    def __init__(self, engine: Engine, render: Render, tokenize: Tokenize, *, budget_bytes: int,
                 clock: Callable[[], float] = time.monotonic, log: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.engine, self.render, self.tokenize = engine, render, tokenize
        self.budget_bytes, self.clock = budget_bytes, clock
        self.log = log or (lambda record: None)
        self.parked: dict[str, Parked] = {}      # session key -> its one checkpoint
        self.pending_delete: set[str] = set()    # checkpoint ids the runtime reported in_use

    # -- the token prefix a request stands for -------------------------------------------------------------
    def prefix(self, view: list[dict[str, Any]]) -> list[int]:
        """The exact token prefix of a request: the view ctxkeeper would send, rendered and tokenized."""
        return self.tokenize(self.render(view))

    def checkpoint_id(self, session: str, tokens: list[int]) -> str:
        return f"{session}-{prefix_hash(tokens)[:24]}"

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
        if manifest.get("label") not in ("experimental", "qualified-one-card"):
            return "label"
        return None

    def before_request(self, session: str, view: list[dict[str, Any]]) -> Decision:
        tokens = self.prefix(view)
        p = self.parked.get(session)
        if p is None:
            return Decision("prefill", "no checkpoint for this session", total_tokens=len(tokens))
        manifest = self.engine.inspect(p.checkpoint_id)
        if manifest is None:
            del self.parked[session]
            return Decision("prefill", "checkpoint gone", total_tokens=len(tokens))
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
        status = self.delete(p.checkpoint_id)
        self.log({"event": "checkpoint dropped", "session": session, "checkpoint": p.checkpoint_id, "why": why, "delete": status})
        return Decision("prefill", why, total_tokens=len(tokens), dropped=p.checkpoint_id if status == "ok" else f"kept: {status}")

    def delete(self, checkpoint_id: str) -> str:
        status = self.engine.delete(checkpoint_id)
        if status == "in_use":
            self.pending_delete.add(checkpoint_id)
        else:
            self.pending_delete.discard(checkpoint_id)
        return status

    # -- parking: one checkpoint per session, bounded in total ------------------------------------------------
    def park(self, session: str, view: list[dict[str, Any]], reply_tokens: list[int] = ()) -> Parked | None:
        """Save the session at the end of its turn (the runtime blocks at a decode boundary), replace the
        session's earlier checkpoint once the new one is visible, then keep the total under budget.

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
            old.last_used = self.clock()
            return old
        manifest = self.engine.save(cid, tokens)
        size = sum(int(b.get("bytes", 0)) for b in manifest.get("blobs", []))
        self.parked[session] = Parked(cid, len(tokens), size, self.clock(), manifest)
        if old is not None:
            self.log({"event": "checkpoint replaced", "session": session, "old": old.checkpoint_id, "delete": self.delete(old.checkpoint_id)})
        self.log({"event": "session parked", "session": session, "checkpoint": cid, "tokens": len(tokens), "bytes": size})
        self.evict(keep=session)
        self.retry_deletes()
        return self.parked[session]

    def total_bytes(self) -> int:
        return sum(p.bytes for p in self.parked.values())

    def evict(self, keep: str | None = None) -> list[str]:
        """Least recently used sessions go first until the parked bytes fit the budget; `keep` is never
        evicted; a checkpoint the runtime holds in use stays and is retried later."""
        gone: list[str] = []
        for session in sorted(self.parked, key=lambda k: self.parked[k].last_used):
            if self.total_bytes() <= self.budget_bytes:
                break
            if session == keep:
                continue
            p = self.parked[session]
            status = self.engine.delete(p.checkpoint_id)   # not a drop: an in-use one stays tracked, no retry
            if status == "in_use":
                continue
            del self.parked[session]
            gone.append(session)
            self.log({"event": "checkpoint evicted", "session": session, "checkpoint": p.checkpoint_id, "bytes": p.bytes})
        return gone

    def retry_deletes(self) -> None:
        for cid in list(self.pending_delete):
            self.delete(cid)

    def status(self) -> dict[str, Any]:
        return {"sessions": {k: {"checkpoint": p.checkpoint_id, "tokens": p.tokens, "bytes": p.bytes} for k, p in self.parked.items()},
                "bytes": self.total_bytes(), "budget": self.budget_bytes, "pending_delete": sorted(self.pending_delete)}


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
