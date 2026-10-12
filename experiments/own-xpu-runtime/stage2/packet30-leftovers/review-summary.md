# Independent summary, registry and window review

The attention-family reviewer read `summary.py`, `class-registry.json`,
`test_protocol.py`, `window.py`, `window_safety.py`, G3's emitted JSON schema,
the packet27 dispatch resolver, and the source W2c class-time file. No native
binary or device discovery was run. The final CPU protocol suite passes
**37 tests**, including the new baseline launch-identity regression below.

## Evidence and arithmetic of the report

The summary requires two distinct completed owners, their clean ownership
teardown, matching output hashes, exact bytes and all required modes. Route
requires finite, tied and rejected-NaN fixture modes. A failed candidate is
excluded individually; successful candidates remain eligible when the native
receipt honestly records other finite-element failures. The native/window
schema matches the fields G3 and the supervisor actually write.

There must be200 complete repetitions per owner/variant, with every declared
event index present exactly once. Group times sum GPU event durations before
computing median and p90. Group-count multipliers use `groups/tokens`, not
individual kernel launch counts. Candidate and incumbent payload/rotation
identity must match, and payloads above8 MiB require eight rotating copies.
The writer rehashes sealed inputs, both owner receipts/exactness/timing files,
and same-identity K0 before producing any measured dispatch proposal.

A baseline must match its registered per-group time within15% in both owners.
The candidate must save at least10% in each. A qualified row uses the smaller
owner saving times the registered groups/token. This is explicitly fixture
kernel-time accounting, never a measured model throughput claim.

## Grouped dispatch and overlapping work

Both `hc.a.norm` and `hc.f.norm` must qualify with the same candidate before
the norm-family key is proposed. The two mix classes follow the same rule.
Both small-FFN formats must qualify before `fusions[small.ffn]` is emitted;
Q6 contributes47 groups/token and Q8 contributes1, avoiding the48-times-each
mistake. Attention contributes12 groups/token, route48 and small.hc96.

A combined attention/norm proposal consumes both `attn.combine` and
`hc.f.norm`. The norm-family proposal consumes both norm resources. Their
intersection is detected and neither is selected by default. Explicit choices
must remain pairwise disjoint; selecting both is rejected. Reported selected
savings sum only selected disjoint proposals, not every individually qualified
row. No double counting was found in the grouped resource accounting.

The HC gate and shared-down anchors correctly remain null after switching
the incumbent to packet28 wg32. Their old in-model times and G2 fixture times
are retained as labeled context, not silently used as replacement anchors.
The FFN-combine/next-layer-norm anchor is likewise null because initial/final
and PLE boundaries prevent simply pairing all48 aggregate class means. These
rows can retain measured fixture diagnostics but cannot qualify a dispatch or
contribute saved milliseconds until the missing matched evidence exists.

## Findings resolved

1. The original summary checked candidate launch counts but accepted any
   internally consistent incumbent count with a plausible duration. The final
   code also requires incumbent launches/group to equal the registered runtime
   identity. A new hostile test preserves the100 us group sum while replacing
   two incumbent events with one, and verifies rejection. All37 tests pass.
2. The initial documented env-i commands hid the only `python` executable on
   this host and omitted the user-service bus environment. The final commands
   explicitly use `/home/steve/.local/bin/python`, retain its PATH entry, and
   provide `/run/user/1000` plus its bus address. Read-only inspection confirmed
   the Python symlink and user bus exist. The shell allowlist admits those keys;
   the native allowlist deliberately strips the service-control-only keys.
3. A generic `classes[norm]` entry would otherwise interact incorrectly with
   the old resolver: existing specific HC keys override it, and broad Op::norm
   fallback includes untested final/PLE sites. Final INTEGRATE instructions
   require an explicit p30 family resolver limited to the tested a/f HC labels,
   preserve final/PLE behavior, and require closed parser/resolver tests. The
   analogous hc.mix family mapping is explicit. This packet does not pretend
   the existing runtime already accepts or executes the new p30 names.

## Remaining boundary

The measured-dispatch output is a proposal for later integration, not a
runtime update. Neither the corrected device commands nor G3 were executed.
Actual device equality, all baseline representativeness checks, safe timing,
and model-level improvement remain pending. No further source-level blocker
was found in the reviewed report/admission logic after these fixes.

## Final failed-candidate isolation review

The wrapper previously required identical whole exactness-file hashes between
fresh owners. That could reject unrelated valid candidates when an already-failed
candidate produced different bad bytes. The wrapper now leaves repeat equality
to the summary's per-qualified-candidate checks. Evidence files remain hash-bound.
A regression fixture makes the rejected candidate differ between owners while
requiring the other candidate to qualify. All 38 protocol tests pass.

The independent attention reviewer inspected the wrapper diff and summary logic
and found no issues: qualified candidates still match their incumbent and the
other fresh owner; failed candidates cannot qualify or block unrelated candidates.
This Python-only correction leaves native binaries, compiled source dependencies,
and CPU family evidence unchanged; see `protocol-revalidation.json`.
