"""Arm B32ira-free: archive-and-recall with FREE-TEXT notes (for LongMemEval and other non-ledger streams).

B32ira (clm_improved.ClmImprovedAgent, fold_mode=read, archive=true) is worded and checked for counters:
STATE.txt lines must match `^[a-z]+\\d\\d\\s+(-?\\d+|removed)$`, a counter line may never vanish, and
`ctxfold --drop` refuses while the item names `[a-z]+\\d\\d` tokens without a STATE line (chat text has
such tokens: covid19, rtx30). This subclass keeps everything else of the improved agent (room gate, pinned
STATE.txt shown every turn, delivered items never rolled back, repeat/answers guards, text-call recovery,
per-call thinking policy, archive-on-drop and `recall`, improved_stats.json) and changes only:

  * notes rule: STATE.txt holds free-form lines, capped at state_max_tokens (default 6144); an edit over the
    cap is rejected and the previous version restored (the existing _validate mechanism);
  * STATE.txt may change only while a newly delivered item is in context (the read-mode guard (d), kept);
    the counter-specific guard (b) "a counter line never vanishes" is off (notes may be rewritten freely);
  * `ctxfold --drop` always runs with `--force` semantics (a shim in front of the unchanged ctxfold.py), so
    the item is archived verbatim and dropped without the counter-name check;
  * the system protocol text is for notes about a person and their history, not counters.

The archive and `recall` are unchanged (recall.py, ctxfold.py's archive-on-drop). Nothing in clm_improved.py,
ctxfold.py or run-context-job.sh is modified: run-context-job.sh runs `improved` with the read-mode/archive
environment and longmemeval-run.sh appends `-a clm_freenotes:ClmFreeNotesAgent` to the harbor arguments
(harbor's --agent is a single-value option: the last one given wins; run-context-job.sh passes its extra
arguments after its own -a). The job's settings.txt still names ClmImprovedAgent; the driver records the
real class in <job>.arm.txt, and improved_stats.json says fold_mode "free".
"""
from __future__ import annotations

from typing import Any

import clm_improved as _ci
from clm_improved import ClmImprovedAgent

PROTOCOL_FREE = """

## Working protocol for streamed data (read carefully)

- Keep your notes in `/tmp/.live_ctx/STATE.txt`: free-form lines, at most about {cap} tokens in all. It is
  part of your context: the harness shows it in a pinned message every turn. It is NOT a notes file.
- You do not know the final questions in advance. From each item, note briefly what may matter later:
  facts and values (a counter's current value, with the item it was set in), people, places and events, plans,
  and what changed (old -> new, with both items or dates). Keep it compact; merge or shorten older lines
  when space runs low, but keep the current value of every live counter.
- After each item, in ONE command: update STATE.txt with a short inline command (for example a here-document
  or `python3 - <<'EOF'` that rewrites the file), then `ctxfold --drop`, which moves the item verbatim into
  the archive and removes it from your context.
- STATE.txt may change only in the same command as a newly delivered item's update; other edits are rejected
  and the previous version is restored. An edit that makes it longer than the cap is rejected too.
- Before running a command that delivers a large item, make sure there is room for it: the harness refuses
  to run such a command when the item would not fit ("NOT RUN").
- Your earlier thinking is not kept between turns. Keep your thinking to what the current item needs; act
  every turn.
- Write /app/answers.json only after the final item with the questions has arrived, with exactly the keys
  it asks for. The harness refuses an earlier write or submit. The one exception: a PROBE item asks a few
  questions mid-stream; answer those at once under the keys it gives (add to the file, keep every key already
  in it), search the archive first when your notes do not hold the answer, then drop the probe item and go on.
"""

ARCHIVE_NOTE_FREE = """- Every item you drop is kept verbatim in a read-only archive (nothing is lost, only moved out of view).
  `recall PATTERN` prints the archived sentences that match (case-insensitive regex, as `item N: ...`);
  `recall --item N` prints item N (its first line gives the session number and date). Their output enters
  your context like any tool output, so search narrowly. When a question arrives (a PROBE item or the final
  item), search the archive for its key words before answering: your notes may have missed the detail it asks
  about; `recall --item N` gives item N whole when a question names it.
"""

# --drop always forced; everything else passed through to the unchanged ctxfold.py
CTXFOLD_SHIM = r"""#!/bin/sh
# ctxfold shim (arm B32ira-free): `--drop` always runs as `--drop --force` (no counter-name check)
REAL=__REAL__
case " $* " in
  *" --drop "*) case " $* " in *" --force "*) ;; *) exec python3 "$REAL" "$@" --force ;; esac ;;
esac
exec python3 "$REAL" "$@"
"""


class ClmFreeNotesAgent(ClmImprovedAgent):
    """Improved agent, read mode + archive/recall, free-text STATE.txt under a token cap."""

    @staticmethod
    def name() -> str:
        return "clm-freenotes"

    def __init__(self, *args: Any, state_max_tokens: int | str = 6144, **kwargs: Any) -> None:
        kwargs["fold_mode"] = "read"
        kwargs["archive"] = True
        kwargs["quoted"] = False
        kwargs["state_line_regex"] = r"^.+$"          # any non-empty line (empty disables nothing in read mode)
        super().__init__(*args, state_max_tokens=state_max_tokens, **kwargs)
        # "free": _PinnedState's counter guards (b, d) are keyed on fold_mode == "read"; (d) is re-applied
        # in _validate below, (b) is intentionally off. run() then takes the module-level PROTOCOL, which is
        # swapped for PROTOCOL_FREE during the run.
        self.fold_mode = "free"

    def _validate(self, text: str) -> str:
        bad = super()._validate(text)                 # token cap (state_max_tokens) and the permissive regex
        if not bad and not getattr(self, "_item_pending", True):
            bad = ("STATE.txt changed while no new item was in your context; fetch the next item first "
                   "(corrections go into the next item's update)")
        return bad

    async def setup(self, environment: Any) -> None:
        await super().setup(environment)
        shim = CTXFOLD_SHIM.replace("__REAL__", "/usr/local/bin/ctxfold.real")
        await environment.exec(
            command="mv /usr/local/bin/ctxfold /usr/local/bin/ctxfold.real && "
                    "cat > /usr/local/bin/ctxfold <<'SHIM_EOF'\n" + shim + "SHIM_EOF\n"
                    "chmod +x /usr/local/bin/ctxfold /usr/local/bin/ctxfold.real", timeout_sec=60)

    async def run(self, instruction, environment, context) -> None:
        saved = (_ci.PROTOCOL, _ci.ARCHIVE_NOTE)
        _ci.PROTOCOL = PROTOCOL_FREE.format(cap=self.state_max_tokens)
        _ci.ARCHIVE_NOTE = ARCHIVE_NOTE_FREE
        try:
            await super().run(instruction, environment, context)
        finally:
            _ci.PROTOCOL, _ci.ARCHIVE_NOTE = saved
