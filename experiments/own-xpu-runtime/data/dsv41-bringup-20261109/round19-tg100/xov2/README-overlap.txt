Overlap of a prompt block's exchanges with compute ("E"): plan, numbers, risks, the six-card check (2026-11-11)
======================================================================================================================
Helper, CPU only (nothing ran on a card, nothing in the repo touched). Arithmetic: tools/overlap_model.py ->
logs/overlap_model.txt. Six-card check: xov2_layer_test.cpp (build_xov2.sh -> bin/xov2_layer_test), gate_xov2.sh.

In plain words
--------------
* Six-card check done (21:19, by the coordinator): with the planned order, 16-group pulls in matched modes hid 91 % of
  the exchange time at 128-token halves (88-95 % per site), with 0 wrong values. That is above the 70 % go line, so
  the engine patch is worth writing: predicted ~0.62 s off a 3K read at blocks of 256 (5.65 -> ~5.0 s).
* Worth doing: about 0.6 s off a 3K read. With pb-1, reading in blocks of 256 tokens is predicted at ~5.65 s; reading
  each 256-token block as two 128-token halves, with half A's exchanges running while half B computes, gives ~5.0 s
  (range 4.99-5.08 if 85-95 % of each exchange hides; 0.26 s off if only half of it hides). That is above the 0.25 s bar.
* It needs a second queue per card. Only changing the launch order on today's queue hides nothing: that queue starts a
  launch only when the one before it has finished, so a reordered exchange still runs alone. Reordered on one queue,
  the halves cost ~0.18 s more than plain blocks of 256 (the same as reading in blocks of 128).
* The catch is the register mode. A card runs two launches side by side only if both were built for the same register
  count (measured on six cards: 74-95 % hidden in the same mode, 0 % across modes). With pb-1 every matrix kernel is a
  256-register build; attention, norms, the expert gate/up kernels are 128. Both builds of the exchange kernel are
  already in the binary. The plan picks, per exchange, the build and the moment it is queued, so that it lands beside
  a long stretch of the other half's work in its own mode. On card 2 each window is 1.2x to 6.6x the exchange.
* Best at blocks of 256. At 128 it saves ~0.36 s against 128 without it, but that is only ~0.2 s below plain 256.
  At 64 it is not worth it (it lands near plain 256 at best).
* No new flags, no waiting inside compute launches, no remote polling: the exchange kernels, their flags and their
  sequence numbers stay exactly as they are; they only move, in the same order, to the second queue.
* Before the engine patch (~700-900 lines, the largest change on the list), one ~1-minute six-card run decides it:
  bin/xov2_layer_test (section 6).
* Side finding (sent at 20:30): in tp100 the dense prompt module (img8) is back in scratch memory, so the old 6-bit
  forms are fast again (pb-1's 64-token 6-bit gain shrinks to ~0.1 s). It changes nothing here.

Six-card check result (coordinator's gate_xov2, 21:18-21:19, runs/xov2/summary.txt): PASS, go
----------------------------------------------------------------------------------------------------------------
  * 0 wrong values, 0 timeouts on every check line: E16 and T64 on two queues, T64 on one queue, 128- and 64-token
    halves, 60 / 30 layers each, regions reused with no alternation; kernel log clean.
  * DECISION line: half 128, two queues, designed modes, 16 groups: 7,781 us per layer against 7,651 compute only
    (exposed 130 us) -> 91.3 % of the pulls hidden. Half 64: 90.7 %.
  * Per site (E16, the others serial): X1 output-a 88.1 %, X2 output-b 91.5 %, X3 act 95.1 %, X4 FFN rows 91.4 %
    (half 64: 85.0 / 90.8 / 94.5 / 91.5 %).
  * What the design choices buy: same modes but 64 groups 64.9 %; today's pull form (128 registers, 64 groups) on the
    second queue only 44.1 %. Order change alone (one queue): compute + pulls, nothing hidden. A 16-group pull alone is
    18 % slower than a 64-group one (1,771 vs 1,502 us per layer in line), inside the 1.33x the windows allow.
  * With h = 0.87-0.95: E at 256 saves 0.59 / 0.62 / 0.66 s -> a 3K read of ~5.0 s against 5.65 s with pb-1 alone
    (logs/overlap_model_xov2.txt). Decision rule (>= 70 %): write the engine patch.
  * Still open (the engine gate): real kernels instead of busy loops (dense rows are memory / port bound, the busy loops
    ALU only), the pair swaps, the per-half engine state, skew between real cards.

1. What runs where today (one layer of a prompt block, card 2 = 12 heads, the pace card)
-----------------------------------------------------------------------------------------
Segments in tpm_layer's order, with the register mode of their kernels (tp100 binary, zeinfo_tp100.tsv; pb-1 forms
from bench dense3 and tp100), and the four pull exchanges between them (backend_sycl_v41_mt.inc 1237-1810):
  S1 post+pre 128 | norm + dots 128 | q_a, kv rows 256 | q/kv norms 128 | q_b rows 256 | rope 128 | (index layers:
     H16 rows 256 with pb-1, score / top-k 128)
  S2 attention: window append, score, softmax, output, ring commit - all 128
  S3 output-a rows 256 (12-head cards: pair swap XchgPair 128, whole-group rows, pair swap, split-group rows)
  X1 = XchgPull2: output-a rows + attention-mix partials (OWN_MT_DSPLIT)
  S4 attention-mix finish 128 | output-b rows 256
  X2 = XchgPull: output-b rows
  S5 post+pre 128 | norm + dots 128 | router (H16, 256 with pb-1) | route pick + shared gate/up 256 | grouping 128 |
     routed gate/up 128 (all three quant types) | SwiGLU 128
  X3 = XchgPull2: expert act + FFN-mix partials
  S6 routed down (by layer: IQ3_XXS / IQ2_XXS 256, IQ2_S / IQ2_XS / Q2_K 128) | FFN finish 128 | shared down 256 |
     combine 128
  X4 = XchgPull: FFN rows (same region as output-b)
  S7 post (+ next layer's pre) 128
The pulls today: XPullK128 / XPullK128x2 (128 registers, 64 work-groups at these sizes); the 256-register builds of
the same XchgPull / XchgPull2 code are the OWN_XPULL_GRF=256 lambdas, also in tp100. XchgPair: 128 only.

Card 2, per read (pp97 profiles, tp97; prompt97/tables/exchanges_b64.txt), and per pull:
  block   XchgPull2  XchgPull  XchgPair  all     per pull (64 groups, incl. waiting for peers)
  64      0.565 s    0.422     0.039     1.027   X1 93 us, X2 / X4 90, X3 179
  128     0.535      0.400     0.034     0.969   X1 175 us, X2 / X4 171, X3 340
  256     0.565      0.383     0.031     0.978
(X1 / X3 split of XchgPull2 and X2 / X4 / engram split of XchgPull by their byte floors; no prompt-block timeline
exists, OWN_TIMELINE covers answer steps only, so these are the profile's per-launch times.)

2. Second queue, or a different order on today's queue?
-------------------------------------------------------
A second in-order queue per card (same context, same device), with every exchange kernel of that card on it in
program order. Plus a new launch order on the compute queue: the order decides what each exchange hides behind.
Recommended: both, as in section 3.
  * Order alone hides nothing. The engine's queues are in-order: the card starts a launch only after the previous one
    has finished (one card, xov/conc.log: big + small kernel on one in-order queue 30.00 ms = the sum; the E pattern on
    one queue 24.7 ms = the sum). Two halves on one queue = blocks of B/2 with pulls in line: at 256 that is
    C(128) + X(128) + gaps(128) = 5.83 s against 5.65 for plain 256, i.e. 0.18 s worse.
  * Two queues work when the exchange is queued before the compute it should overlap and both are the same register
    mode (xov/conc.log, xov/grf.log; six cards with real peer pulls, runs/xov1: 74-95 % hidden at 16 work-groups in
    the same mode, 50-78 % at 64, about 0 % across modes, 0 wrong values in 400 iterations of every shape). A pull can
    overlap several consecutive compute launches (grf.log E pattern: 24.68 -> 20.17 ms beside four 4 ms launches).
  * Pull work-groups riding inside the compute launches (xov design 4.6, plan B) are out: that is a wait inside a
    compute launch, the pattern that hung two cards in qb-off-2 / 3.
  * An out-of-order queue would also overlap, but the exchanges could then publish out of order (the flags test
    flag < seq); not considered further.

3. The plan
-----------
Block of B tokens = two halves A (tokens 0..B/2-1) and B (B/2..B-1). Each half runs today's launches for B/2 tokens
(the kernels, forms and sums of a block of B/2 at those positions: bit for bit what blocks of B/2 give today; the
traces are byte-identical across block sizes 1..256 incl. 129 / 255). q1 = today's queue, q2 = the new exchange queue.
Per layer, card thread order (every card the same; "-> q2" = queued on q2 at that point, after a depends_on the last
q1 launch; "wait" = q1 waits on that exchange's event before its consumer):

  wait X4(A, L-1); S7(A) post; S1(A); -> q2 X4(B, L-1) [128]; S2(A) attention; S3(A) output-a (+ pair swaps on q2)
  wait X4(B, L-1); S7(B); S1(B) post+pre, norm+dots; -> q2 X1(A) [256]; S1(B) q_a, kv, norms, q_b, rope, index;
      S2(B); S3(B)
  wait X1(A); A's attention-mix finish; -> q2 X1(B) [256]; A's output-b rows
  wait X1(B); B's finish; -> q2 X2(A) [256]; B's output-b rows
  wait X2(A); A's post+pre, norm+dots, router, route pick + shared gate/up; -> q2 X2(B) [128];
      A's grouping, routed gate/up, SwiGLU
  wait X2(B); B's post+pre, norm+dots, router, shared; -> q2 X3(A) [128]; B's grouping, routed gate/up, SwiGLU;
      -> q2 X3(B) [layer's routed-down mode]
  wait X3(A); A's routed down, FFN finish, shared down, combine; -> q2 X4(A) [routed-down mode]
  wait X3(B); B's routed down, FFN finish, shared down, combine
  (next layer)
Exchange order on every card: X4(A,L-1) X4(B,L-1) pair(A) X1(A) pair(B) X1(B) X2(A) X2(B) X3(A) X3(B) X4(A) ...

Per site: what is independent, what it hides behind, and how long (card 2, us; pull today = 64 groups incl. waiting;
16-group pulls are up to 1.33x slower alone (xov1 rates), so the windows are checked against 1.33x; window = the
same-mode compute of the other half, Q8 layers, pb-1 picks; Q6 layers in brackets):
  site   needed by (same half)          independent work it sits beside  mode  128-token halves      64-token halves
  X1(A)  A's finish + output-b          B's q_a + kv rows                256   232 vs 317 (1.4x)     123 vs 188 (1.5x)
  X1(B)  B's finish + output-b          A's output-b rows (A's finish    256   232 vs 277 (1.2x)     123 vs 162 (1.3x)
                                        moved before it)                       [Q6 307]              [Q6 147]
  X2(A)  A's post+pre .. router         B's output-b rows                256   227 vs 277 (1.2x)     119 vs 162 (1.4x)
  X2(B)  B's post+pre .. router         A's grouping + routed gate/up    128   227 vs 1500 (6.6x)    119 vs 800 (6.7x)
                                        + SwiGLU (queued after A's
                                        router + shared, 256)
  X3(A)  A's routed + shared down,      B's grouping + routed gate/up    128   452 vs 1500 (3.3x)    238 vs 800 (3.4x)
         FFN finish                     + SwiGLU
  X3(B)  B's routed down ..             A's routed down                  m_L   452 vs ~890 (2.0x)    238 vs ~450 (1.9x)
  X4(A)  A's post (next layer)          B's routed down                  m_L   227 vs ~890 (3.9x)    119 vs ~450 (3.8x)
  X4(B)  B's post (next layer)          next layer's A attention         128   227 vs 281 (1.2x)     119 vs 147 (1.2x)
                                        (queued after A's q_a .. q_b)
  pair   split-group output-a rows      - (stays exposed: 0.03 s)        128
  engram per block (3 pulls)            - (stays exposed: 0.04 s)        128
  m_L = the layer's routed-down mode (18 layers 256, 22 layers 128). Every half-B consumer comes after the matching
  half-A consumer on q1, so each pull's window ends before its consumer starts.
Dependencies between the halves that involve no exchange: B's attention reads A's key rows (ring), A's compressed
rows (publish) and index state, all written earlier on the same card's q1 - the order above keeps them first.

Why it stays bit for bit: no sum changes. Each half is a block of B/2 tokens at its positions; the exchanges copy
finished floats; the kernels are today's kernels. The register-mode choice of a pull changes its code, not what it
copies (copy only).

Why the exchange protocol is unchanged and cannot deadlock: all of a card's exchanges stay on one in-order queue in
the same program order on every card, so flags are still published in sequence order (the flag < seq test). A pull
publishes at its start, which is after the card's previous exchange completed, which needed every peer's publish of
the one before: every wait points to earlier work in every card's own order. q1 has no waits inside launches; it
waits only (host-side events) on exchanges queued before that wait. Region reuse (write after read), per region:
  output-a (A slot) written by A's next-layer output-a rows: after "wait X4(A, L-1)" -> every peer has published
  X4(A, L-1) -> finished X1(A, L-1) (its last read of that slot). Output-b slot (output-b rows and FFN rows share it):
  A's FFN rows written after "wait X3(A)" -> peers finished X2(A); A's next output-b rows after "wait X1(A, L+1)" ->
  peers finished X4(A, L). Act slot: A's SwiGLU after "wait X2(A)" -> peers finished X3(A, L-1). B the same.
  xov2 checks this with real pulls and no alternating regions (section 6).
Per-half state the patch must split (xov/design.md 4.4): the scratch views at token t0 (scm[c][t0]), positions and
lens, WindowAppendM / RingCommitM / publish / index per half in order, the expert groups (egrp: two copies, A's are
still read by A's routed down after B's grouping), eu_cap from the half's m, ds_split per half (partial regions at
the half's tokens), lay_m(m), use_pull / xp_oa_m from m, the engram pull once per block, the head after both halves.
Every pull call takes a mode (128: XPullK128 / XPullK128x2, 256: the lambda builds) and 16 work-groups.
Opt-in (OWN_XOV=1), prompt blocks of >= 2 x OWN_XOV_MIN tokens; checks and answers keep today's path.

4. Numbers (card 2 per read, pb-1 on; logs/overlap_model.txt)
---------------------------------------------------------------
Inputs: pp97 kernels / exchanges (tp97), pb-1's predicted card-2 savings (README-pb1: 0.49 / 0.94 / 1.08 s at
64 / 128 / 256), unprofiled 3K walls (6.80 / 6.77 / 6.73 s). With pb-1: non-exchange kernels C = 5.12 / 4.77 / 4.61 s,
reads 6.31 / 5.83 / 5.65 s. Hidden share h = 0.85-0.95 (xov1, same mode, 16 groups, windows longer than the pull).
  E at block B: halves of B/2 run B/2-token kernels and B/2-token pulls.
    saving = h x (hideable pulls at B/2) - [C(B/2) - C(B)] - [X(B/2) - X(B)] - [gaps(B/2) - gaps(B)] - waits
  block   hidden          kernels at B/2   exch. launches   gaps     waits    saving (h .85/.90/.95)   read with E
  256     0.76-0.85 s     +0.156           -0.009           +0.033   0.006    0.57 / 0.62 / 0.66 s     4.99-5.08 s
  128     0.80-0.90       +0.351           +0.058           +0.071   0.012    0.31 / 0.36 / 0.40       5.43-5.52
  64      ~0.89-0.99      +0.05..0.35 est. +0.116           +0.08    0.025    0.32 .. 0.73             5.58-5.99
  (64: no 32-token profile on tp97+; the range spans tp88's 32-vs-64 read (+0.06 s) and pb-1's 128 -> 64 step.)
  Best: E at 256, ~5.0 s (about 660 tok/s) against 5.65 s for pb-1 alone. If only 50 / 60 % of each pull hides:
  0.26 / 0.35 s.
  Per site at 256 (h = 0.9): X3 act 0.32 s, X1 output-a 0.16, X2 output-b 0.16, X4 FFN rows 0.16; exposed: pair swaps
  0.03, engram pulls 0.04, the unhidden 10 % 0.09.
Where the kernel cost of halving comes from (pb-1 picks, README-pb1 bench; us per token per launch, 64 / 128 / 256):
  Q8 q_a 2.09 / 1.77 / 1.91; kv 0.84 / 0.70 / 0.72; q_b 2.38 / 2.34 / 2.45; o_a 1.37 / 1.21 / 1.21; o_b
  2.53 / 2.16 / 2.08; shared gate+up 1.22 / 1.06 / 1.10; shared down 0.89 / 0.63 / 0.56; Q6 o_b 2.30 / 2.40 / 2.13;
  engram 7.9 / 8.7 / 8.1; H16 router 0.57 / 0.56 / 0.43; experts gate+up (pp97, s per read) 1.680 / 1.557 / 1.492,
  down 1.036 / 1.016 / 0.997. So 128 against 256 costs little (+0.16 s per read, half of it the experts' fewer
  shared decodes), 64 against 128 costs +0.35 s (the dense forms are 10-15 % cheaper per token at 128).
Launches: E at 256 runs 1,524 launches per half-block (as blocks of 128) instead of per block: +~20K per read, their
fixed cost is inside the 128-token kernel times above, plus the host gaps (+0.033 s). Cross-queue: 2 per pull, 8 per
layer on q1's path (~1.5 us each assumed, 6 ms per read at 256; the one-card xov2 run measures it).

5. Risks
--------
 1. Register mode (measured): a 128- and a 256-register launch never share the card. If a window turns out to be the
    other mode, that pull runs alone (today's cost + two mode switches, ~3 us each). Modes are read from the built
    binary (tools/zeinfo.py); the per-site mode is a host table; pb-1's table changes can move a role between modes.
 2. Tight windows: X1(B), X2(A), X4(B) have 1.2x the 16-group pull on card 2. Card skew beyond ~40-50 us at those
    sites shows as waiting (never worse than today). The 8-head cards' attention is 2/3 as long, so X4(B) exposes
    ~40 us per layer there; they carry ~130 us per layer less work, so they stay off the critical path.
 3. Hang: no new flags, no waits inside compute launches, peer reads only by the existing XchgPull / XchgPull2 /
    XchgPair, flags published in sequence order (one in-order exchange queue per card). It relies on this driver
    feeding both queues to the one engine in submission order (measured: xov conc / grf / xov1). A driver that
    time-slices two queues would make spinning pulls cost compute time (slower, still right): re-run xov2 after any
    driver or oneAPI update.
 4. Wrong values from the per-half state (egrp copies, partial regions, positions, publish order): the trace gate
    (byte-identical to the reference at blocks of 64 / 128 / 256 and odd sizes) catches them.
 5. Write after read on the reused regions: argued per region in section 3; xov2 tests it with real pulls.
 6. Host resets (I210 / PCIe, 11-10 / 11): E adds no peer bytes and 16-group pulls lower the peak rate, but peer
    traffic now runs during compute. Short runs, fault grep after each.
 7. The halving cost rests on pb-1 at 128 vs 256 (tg100 measures it). tp100's img8 back in scratch moves the 6-bit
    numbers at every block size by similar amounts; the conclusion (E at 256) does not depend on it.
 8. Threads: a 16-group pull holds 6 % (128) / 12.5 % (256) of the card's threads while it runs; xov1 lost 5-16 % of
    the pull time to that (inside h).
 9. Size: ~700-900 lines of backend_sycl_v41_mt.inc (tpm_layer split into segments taking (t0, m), the per-half
    driver, q2 and its events, per-site modes). Default off; with OWN_XOV unset every launch stays as today.
10. Proof of overlap in the gate: OWN_GPROF profiling events on both queues (q2 needs enable_profiling) show each
    pull's start / end against the q1 launches; OWN_TIMELINE does not cover prompt blocks.

6. The smallest six-card check (for the coordinator's next gate; three short runs, ~2 minutes with the pauses)
------------------------------------------------------------------------------------------------------------
bin/xov2_layer_test (source xov2_layer_test.cpp, built by build_xov2.sh from the tp100 snapshot's headers). It runs
the per-layer order of section 3 on all six cards with the engine's XchgPull kernel unchanged on a second queue,
busy kernels in place of the compute segments (card 2's lengths and modes at 128- and 64-token halves), one region per
site reused every layer (output-b and FFN rows share one, as in the engine), every gathered row checked, each pull in
its designed mode (X3(B) / X4(A) alternating 128 / 256 by layer). No deliberately stuck exchange.
gate_xov2.sh (takes six.active, waits for empty locks, kernel-log fault check after each run, 30 s between runs):
  d128  60-layer check (E16, two queues); time per layer: compute only, one queue (the halves' order with pulls in
        line = order change alone), two queues E16 / E64 / T64 with exposed time and hidden share; per site (E16):
        hidden share of X1 / X2 / X3 / X4 with every pull still on the second queue in order (the other sites made
        serial) - ~7 s of exchange traffic
  d64   the same at 64-token halves - ~4 s
  c     the other checks (T64 on two queues, T64 on one queue, both sizes) - ~3 s
  Each run stops itself after 25 s (STOP_TIME); timeout 60 s per run.
Pass: 0 wrong values and 0 timeouts on every check line, no STOP_TIME, clean kernel log.
Decide on the summary's DECISION line ("half 128 two queues E16 ... hidden NN %"):
  >= 70 %  -> write the engine patch (predicted >= 0.45 s at 256);
  50-70 %  -> 0.26-0.45 s: still above the bar, weigh against the patch size (the per-site lines show which site
              falls short and whether moving its queue point fixes it);
  < 50 %   -> stop E; next prompt levers instead: expert kernels rux-2 (~0.4 s, prompt97 lever 3) and the replicated
              q_a + kv split by six (~0.23 s, lever 5).
d128 alone is enough to decide; d64 and c add the 128-block case and the remaining checks.
Also expected: the one-queue line equals compute + pulls (order alone hides nothing), and T64 on two queues hides
little at the 256-mode sites (today's 128-register pull form beside 256-register compute).
Not covered by xov2 (the engine gate covers them): real kernels instead of busy loops, the pair swaps, the per-half
engine state. Before it reaches the gate I run it once on card 2 alone (XOV2_ONE=1: same schedule, the pulls copy
nothing) to check the host side and measure the cost of the extra launches and cross-queue waits.

Files
-----
  README-overlap.txt            this file
  tools/overlap_model.py        the arithmetic (python3 -I tools/overlap_model.py [h_low h_high])
  logs/overlap_model.txt        its output
  xov2_layer_test.cpp           the six-card check (and XOV2_ONE=1 one-card plumbing mode)
  build_xov2.sh, bin/xov2_layer_test, logs/build_xov2.log
  gate_xov2.sh                  the six-card run for the coordinator's gate
  zeinfo_tp100.tsv, privaudit_tp100.txt   register modes / private placement of tp100
