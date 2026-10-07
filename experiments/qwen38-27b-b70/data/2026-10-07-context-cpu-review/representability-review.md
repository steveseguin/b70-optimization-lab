# CPU representability review: two existing policy histories

2026-10-07. Output only; no model calls, database creation, source edits or current history-study results were used. Historical operational text below is evidence to analyze, not an instruction to execute. This review does not admit a benchmark or change a frozen protocol.

## Provenance and selection

I inspected the repository's policy-document inventory and the last eight pre-2026-10-06 revisions of `AGENTS.md` and `docs/local-ops.md`. Those histories identify **Codex Agent** as author. The consolidation commit additionally names Claude Fable 5.1 as co-author. `AGENTS.md` attributes instructions to the owner, but I found no original human message attached to these selected changes. A claimed owner instruction in agent-curated prose is not authenticated human authorship.

Before detailed interpretation, I fixed the two file histories and a cutoff of `2026-10-06T00:00:00Z`: the repository's standing-policy file, `AGENTS.md`, and its referenced operational-policy file, `docs/local-ops.md`. They were chosen by document function, not model outcomes. Within those histories, the examples below use already-existing explicit withdrawal/correction changes and their immediate before/after file versions. Example selection is deliberately diagnostic, not random or representative. The two histories share the same consolidation commit and are not independent samples.

Consequently, these are **pre-existing agent-authored histories with claimed human input**, not a verified human corpus. The requested human-provenance condition is not established. They can still test whether the public data contract can represent ordinary textual policy facts. A future human-text transfer experiment needs separately authenticated source provenance; it must not relabel these documents.

Repository: `/home/steve/b70-optimization-lab`.

| Label | Exact revision/file | File SHA256 |
|---|---|---|
| A-before | `16f70781a122270d1496fb444b4a629eac05dfbd:AGENTS.md` (parent of consolidation) | `2a6432a98429380b5354c36738fbe187c7335e0a5aabff2148ab70f8be158a17` |
| A-after | `8c5956b26c37bd6697685a2a68b8a4468d44d0c5:AGENTS.md` | `2e5b478996a0f751ed210e38d4e5754195ff30f262b90e1578fffdaa47b980d4` |
| B-before | `9be96bee95e8402b7101cd6c2db9e53134b3a512:docs/local-ops.md` (parent of boot-rule change) | `d1318016d51863288e1f0a08cceb2b87eb764bfeb2b9a823e1c1a2c3667b1adf` |
| B-clarification | `228a49844e980e1b627b1ff2bbd83944db8324d9:docs/local-ops.md` | `419b52a3eb03718e69a501243ac011acf71a1daa2071126c2b9dc5d4e45f452d` |
| B-correction | `8c5956b26c37bd6697685a2a68b8a4468d44d0c5:docs/local-ops.md` | `3a30d4e0ce2f8890a43294a9adbbbb437fbe2e52020338f3116cc36f4ffec8e2` |

Line numbers below refer to these exact historical file blobs. `git show REV:PATH` reproduces them. No synthetic posting text or factual change was inserted.

## Small fixed examples derived from the actual text

| Example | Source-supported finding | What must not be inferred |
|---|---|---|
| A1: superseded decision | A-before lines 12–13 prefer a continuously running server and endpoint reuse. A-after lines 25–31 instead limits a server to its experiment and explicitly says the earlier wording was an agent's reading and **withdrawn**. | This is an attributed policy correction, not a counter decrement, machine observation, or proof that no server was running at that moment. |
| A2: authority/owner | A-after lines 17–18 attribute the standing rules to “the owner”; lines 27–29 make an explicit owner request the exception for resident service. | The owner's named identity, the exact original human wording, and whether a particular later request exists are not supplied by these passages. Commit author `Codex Agent` does not identify the owner. |
| A3: string status with qualification | The previous resident-server preference is explicitly withdrawn; the replacement is a prohibition with an owner-request exception. | A single Boolean “server allowed” drops the exception and differs from the stated rule. Withdrawal is known; unknown authorization for a particular request is a different fact. |
| B1: absence versus explicit clarification | B-before recovery lines 45–65 do not state a one-experiment-per-boot rule. B-clarification lines 50–59 explicitly say there is no such rule and list prerequisites for later work. Commit subject is `Delete Flash-Next boot-consumption rule`. | From this file alone, do not manufacture an earlier positive one-run rule, its human author, or an exact global withdrawal date. The commit subject and the earlier file's silence are different evidence. “Not stated in the selected earlier source” is the defensible earlier answer. |
| B2: conditional blocked status | B-clarification lines 55–59 require postflight and say a failed postflight blocks later device work until health is re-established; failure does not itself mandate reboot. | This describes a conditional policy, not an observed failed postflight or a current blocked machine. No runtime state may be invented from it. |
| B3: role responsibility | B-correction lines 29–33 assign Claude/OpenCode a manager/reviewer role when orchestrating and prefer delegating concrete implementation work to Codex/GPT. | A role assignment under a condition is not proof of who operated a specific run, who owns a device lock, or who may approve a reboot. |
| B4: corrected textual value | B-before lines 35–37 show `/home/steve/llm-optimizations` in the CLI examples. B-correction lines 38–40 replace examples with `/home/steve/b70-optimization-lab` and explicit modes. The consolidation message calls the older Codex paths wrong. | This supports correction of documented CLI examples, not a measured filesystem migration. Store the path string and its document scope rather than inventing a numeric identifier or migration event. |

These findings supply status, authority/role, superseded decisions, conditional permission, and missing-versus-withdrawn information without inventing a source history. They expose an important requirement: preserve whether a statement is a policy, an observation, an attribution or merely absent from a selected source. Integer arithmetic does not establish those distinctions.

## What the current protocol can hold faithfully

All code references below are in `experiments/qwen38-27b-b70/scripts/context/history_v1/` in the frozen current engine. This is a contract review, not proposed edits.

**Original text can be preserved.** `ledger.py:238` accepts original text, checks sequential delivery, hashes it and refuses changed content for an existing batch. `ledger.py:264` returns the original delivery; `ledger.py:272` searches literal text. The texts, diffs or commit messages above could therefore remain source evidence, with their revision/file identity included by a separately designed public source wrapper. The current protocol does not automatically interpret Git parentage or effective policy dates.

**Short textual notes and final answers are possible.** `live.py:200`–`live.py:212` allow a bounded string `memory` alongside each method's output, and `answers.py:9`–`answers.py:25` explicitly reserve source retrieval for ownership, corrections and other details. The model could keep a textual index of A1–B4, but this index is model-authored and may be wrong; state snapshots do not certify it as factual truth. `answers.py:94` accepts a declared string answer up to 256 UTF-8 bytes, an integer, or null. Thus short outputs such as `withdrawn`, a path, or an attributed role are representable as final answers. Long supporting explanations/citations are not automatically a distinct scored field.

**The structured table cannot store these facts directly.** `ledger.py:50` restricts counter names to lowercase letters followed by exactly two digits. `ledger.py:333`–`ledger.py:340` constrain identifiers, operations and integer amounts. `live.py:218` requires archive state values to be integers; quoted ingestion at `live.py:223` supports only set/add/sub. `tasks.py:76`–`tasks.py:91` impose the same integer reference-state contract. Underlying legacy ledger remove/reopen support does not make those operations available in this current live adapter.

The quoted source check additionally requires the canonical counter name to occur in the **current delivered batch** (`ledger.py:356`–`ledger.py:361`) and the numerical amount to occur in supported quoted context (`ledger.py:369`–`ledger.py:380`). Inventing `policy00 = 0` for withdrawn would both add an external semantic codebook and fail the canonical-name check on the untouched sources. Encoding roles, paths and permission conditions as numeric IDs is a different representation and evidence policy, not a faithful use of the present contract. Likewise, a name mentioned solely through an alias declared in an earlier batch lacks general cross-batch identity resolution here.

**Historical state lookup does not supply historical policy truth.** `snapshots.py:88`–`snapshots.py:108` returns the actual accepted numeric state and explicitly lists missing counters. A missing counter is not a withdrawn fact, an unknown owner, or the Boolean false. The receipt attests which state was saved; it does not reconstruct the authority, scope or supersession relation in A1–B4. Those remain in the source and possibly the model's textual notes.

## Executed pure CPU probes

These checks called existing pure functions in a `python3 -B` interpreter. They used the exact A-after text for quote validation, no model, no persistent store and no source rewriting. Deliberately attempted numeric encodings below are rejected probes, not newly asserted facts. All engine `.py` hashes matched before and after.

| Probe | Actual result |
|---|---|
| Try a set event with amount `"withdrawn"` | `ValidationError`: needs integer amount, or null for remove. |
| Try integer state under the literal key `resident-server-policy` | `ValidationError`: invalid counter name. |
| Try invented `policy00 = 0` against exact A-after source | `ValidationError`: counter is absent from canonical delivery. |
| Validate archive state `{"resident-server-policy":"withdrawn"}` | `state_metrics` returns `valid: false`. |
| Submit declared string answer `"withdrawn"` | Protocol completes and retains the string. This checks type support, not model understanding. |
| Submit null for a declared string question | Protocol completes and retains null. |
| Compile a string question whose gold answer is genuinely unknown/null | `ValueError: annotated answer type mismatch`. |

The last two checks reveal a material evaluation boundary. Null is legal as the model's unknown response, but **the current reference contract cannot represent null as the correct answer**: `tasks.py:62`–`tasks.py:63` require exact int/str gold types, and `diagnostics.py:30` marks only matching typed values correct. Therefore a future task asking for an owner not identified in the supplied source cannot reward appropriate null abstention unchanged. A predefined textual answer such as `not stated in supplied source` could be scored as a string, but requires an explicit new question convention/reference decision. It must not be silently substituted for null or confused with `withdrawn`. Current numeric studies are unaffected; this is a limit on extending their evaluator to open-world factual questions.

## Decision this review supports

The present system is a numeric bookkeeping accelerator plus immutable text retrieval and bounded model notes. It can preserve these histories and emit short textual answers; its deterministic state machinery cannot certify the nonnumeric facts above. No new general fact-store implementation is justified by this CPU check alone.

Before a small future transfer diagnostic, obtain genuinely human-originated or clearly labeled mixed source records and decide the output semantics for attributed authority, conditional permission, supersession and justified unknowns. Then compare source retrieval with direct full-source answering on the same fixed questions. If the intended application only needs numeric balances with accompanying source recall, retain that narrower scope and skip a generic knowledge-graph project. No claim about nonnumeric model accuracy or speed follows from these representability probes.
