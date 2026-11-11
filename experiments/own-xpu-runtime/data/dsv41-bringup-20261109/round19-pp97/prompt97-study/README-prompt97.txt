prompt97: ranked levers for reading a 3K prompt faster (DeepSeek V4.1 Flash, six B70, own SYCL engine, tp97)
2026-11-11. CPU-only analysis: no GPU run, no build, no repo edit.

Inputs
  - data/dsv41-bringup-20261109/round19-pp97: byte-identical to /home/steve/dsv41-work/runs/pp97.
  - runs/pp92: the tp92 profiles.
  - runs/tg96b, tg97b, tg97c: the unprofiled 3K reads.
  - runs/xov1: the six-card overlap pre-check.
  - xov/design.md, pa/grf_pr.txt.

Everything survived the 15:17 reset. The tables were regenerated after it.

Full study: README.md. Arithmetic: tools/levers97.py -> tables/lever_estimates.txt.

About the timelines: no prompt-block timeline exists.
  - OWN_TIMELINE records answer steps; OWN_TIMELINE_CHECKS records guess checks.
  - round19-tl85-timeline covers answer steps 20-27 of tp85, and its clock mapping is flagged implausible.
  - So the exchange wait in prompt blocks cannot be split from the copy. This study bounds it from the profile.

IN PLAIN WORDS

Today the 3,323-token prompt takes 6.80 s (489 tok/s).

The bit-identical arithmetic alone needs about 2.0 s. Moving the data the cards must swap adds about 0.7 s. So
today is about 2.5x the hard limit, not 5x. A "5x" figure comes from counting a multiply-add as one fused
instruction (FMA), and FMA rounds differently, so it is not allowed.

The time goes to:
  - expert matrices: 2.7 s
  - the other matrices: 2.0 s
  - card-to-card exchanges, all spent waiting: 1.0 s
  - everything else: 1.0 s

The eight levers below add up to about 2.2 s off: about 4.6 s, or 720 tok/s (range 630-870). All of them keep
the output bit-identical.

FLOORS OF THE WHOLE READ (card 2, the pace proxy)

  Rate used:
    - 11.47 T FP32 ops/s per card (32 Xe-cores x 8 XVEs x 16 lanes x 2.8 GHz).
    - That is 5.73 T multiply-adds/s, because the reference multiplies and then adds (-ffp-contract=off).
    - No FMA, no DPAS.
    - The 230 W cards really run at about 2.6 GHz under load, about 7 % lower.

  floor                                                                    s       today / floor
    strict FP32 (every multiply-add, nothing else)                         1.97    3.4x
    + exchange bytes at 25 GB/s, not overlapped                            2.69    2.5x
    today's tile shapes, exchanges hidden (64 / 256 blocks)                3.35 / 2.79    2.0x / 2.4x
      - dense: x read once per 2 rows through the 8.28 TB/s L1 port
      - experts: weights decoded once per group of up to 6 slots

RANKED TABLE (seconds off the 6.80 s read; low / central / high)

 #  lever                                         kind          saving s            effort  conf.        bit-exact risk
 1  E: exchanges overlapped                       scheduling    0.43 / 0.62 / 0.84  L       medium-low   low (ordering only)
 2  Blocks of 256 done right                      form table    0.30 / 0.44 / 0.50  M       medium       none
                                                  + 2 kernels
 3  Expert kernels (rux-2)                        kernel        0.31 / 0.40 / 0.64  M-L     low          low
 4  Dense forms that lag (H16 rows, Q6/Q5,        kernel        0.23 / 0.30 / 0.35  S-M     medium       low
    tp97 Q6 slowdown)
 5  D: replicated q_a + kv split by 6             kernel table  0.16 / 0.23 / 0.31  M-L     medium-low   none
                                                  + 1 pull
 6  Dense Q8_0 past the x-port cap (R=4 x T=8)    kernel        0.03 / 0.08 / 0.15  M       low          low
 7  Parallel expert grouping (ExpertGroupM)       kernel        0.05 / 0.08 / 0.09  S       medium-high  none
 8  12 / 8 head imbalance                         runtime /     0.02 / 0.06 / 0.12  S / M   low          none
                                                  layout
    all eight, treated as additive                              1.53 / 2.19 / 2.99  -> 5.27 / 4.61 / 3.81 s
                                                                                       (630 / 720 / 870 tok/s)

PER LEVER

1. E: exchanges overlapped
   What changes:
     - Two 64-token halves of a 128-token block are in flight at once.
     - Half A's pulls run on a second in-order queue while half B computes.
   Time now:
     - 1.027 s of exchange kernels on card 2 (15.5 % of its kernel time).
     - Per 64-token block that is 243 launches: 80 XchgPull2, 83 XchgPull, 80 XchgPair. The 8-head cards have 163.
     - Nothing overlaps, so all of it is on the critical path.
     - 0.31 s of it is above the byte + sync floor: round trips plus waiting for slower peers.
   Floor:
     - 0.72 s of copying (17.3 GB per read at 25 GB/s, plus 2.5 us per exchange) if nothing is hidden.
     - About 0 on the critical path if all of it is hidden.
   Saving: 0.62 s (0.43-0.84).
     - Hidden fraction 50-85 %, minus 0.03-0.08 s of cost.
     - Evidence (xov1): 74-95 % hidden with 16 work-groups when the pull and its neighbours use the same register
       mode, about 0 % across modes, 0 wrong values.
     - The halves are 64 tokens each, so every kernel keeps today's 64-token cost.
     - The lever grows as the other levers cut compute.
   Effort: L.
     - 700-900 lines in backend_sycl_v41_mt.inc: per-half state, every exchange moved to the second queue.
     - Two pull builds, at 128 and 256 registers. Most dense prompt forms build at 256 while the pulls are pinned
       to 128, so each overlapped pull must match its neighbours or ride inside them.
   Bit-exact risk: low.
     - The arithmetic is unchanged: the halves are two consecutive 64-token blocks, and traces are byte-identical
       across block sizes.
     - The risk is ordering: a race gives wrong values or a hang. xchg_pull_test and the gate catch it.

2. Blocks of 256 done right
   What changes:
     - Read 256-token blocks, with every role at its best per-token cost.
     - The dense rows use the 64-token T=8, R=2 forms, looped over 256 tokens.
     - The engram and router rows get weight-reusing forms.
     - The expert grouping kernel becomes parallel.
   Time now: kernels 6.633 s at 64 and 6.667 s at 256. At 256 the experts gain 0.23 s, but 0.39 s of penalties
   cancel it (ms per read):
     - router +84: its form reads x once per row; 420 us per launch at 256 against 67 us at 64.
     - grouping +77
     - engram +44: a non-weight-reusing form at 256.
     - q_a / q_b / o_a / route pick +141: the form table picks T=4, R=4 forms at 256, which cost 0.35 ps per
       multiply-add against 0.30.
     - compressor +20
     - post+pre +18
   Floor: the best of 64 and 256 for every role is 6.273 s of kernels.
   Saving: 0.44 s (0.30-0.50).
     - 0.36 s of kernels plus about 0.075 s of fewer gaps.
     - Unprofiled, 256 is already 0.04 s faster than 64 despite 0.034 s more kernel time.
   Effort: M. WsTab picks at M=256, plus an engram WS form, an ExpertGroupM rewrite, and the H16 form from lever 4.
   Bit-exact risk: none. Block size never changes per-token arithmetic, and 256, 129 and 255-token blocks already
   pass TRACE_IDENTICAL.

3. Expert kernels (rux-2)
   What changes:
     - Spill-free two-row forms.
     - Four-row tiles at 128 registers.
     - Weight decode shared by more slots (caps of 8-16, where registers allow).
   Time now: 2.716 s, 41 % of kernel time.
   Floor:
     - Pure FP32: 0.824 s.
     - Issue floor including weight decode (7 instructions per weight per group of up to 6 slots): 1.807 s at 64.
     - At 256: 1.50 s with cap 6, 1.25 s with cap 16.
     - Today's kernels run at 67 % of the issue floor at 64, and 60 % at 256.
   Saving: 0.40 s (0.31-0.64). Reaching 75 / 80 / 85 % of the issue floor saves 0.31 / 0.46 / 0.59 s. This adds to
   lever 2.
   Effort: M-L. Work goes into sycl_v41_routed_rux.hpp; bench_rux already has the real 3K picks.
   Confidence: low. Every K2 packed-lane form was slower. rux-1 took -0.36 s in one step.
   Bit-exact risk: low. The decoded weights, x addresses, per-output multiply-then-add order and final butterfly
   all stay the same. bench_rux checks every output bitwise.

4. Dense forms that lag
   Time now:
     - H16 rows (router, compressor and indexer proj in one kernel type, plus the indexer q_b): 0.287 s.
     - Q6_K / Q5_K layers (13 of 40): 0.220 s above the same shapes at the Q8 per-launch time.
     - The tp92 -> tp97 slowdown of unchanged Q6 forms: 0.059 s.
       o_b WsQ6<32u> went 244 -> 317 us; engram WsQ6<24u> went 575 -> 670 us.
   Floor:
     - H16 rows: 0.082 s at FP32. Today they run at 3.1x / 5.2x of it, because x is loaded once per row:
       4 B per multiply-add through the L1 port.
     - Q6 / Q5: the Q8 per-launch time is a practical floor.
   Saving: 0.30 s (0.23-0.35).
     - H16 weight-reusing form at R=2: 0.144 s. WsH16 forms already exist for 2-3 token checks.
     - 40-60 % of the Q6/Q5 gap: 0.09-0.13 s. The o_b Q6 form at 64 runs T=4 at 4.0x its floor.
     - The tp97 Q6 slowdown: 0.06 s, found from an IGC dump (register mode or spills).
   Effort: S-M.
   Bit-exact risk: low. WS forms keep each output's column order and butterfly (1,560 bitwise checks for
   Q8 / Q6 / Q5). The H16 form needs its own bitwise bench against GemvH16P.

5. D: replicated q_a + kv split across the six cards
   Time now:
     - Every card computes all of q_a (1,280 rows) and kv (512 rows): 0.439 s at 2.1x FP32.
     - The indexer q_b takes another 0.10 s.
   Floor:
     - A sixth share: 0.07 s at today's efficiency, or 0.10-0.15 s allowing for the 213 / 85-row slices being
       1.4-2.0x less efficient per row.
     - Plus one new pull per layer: 382 KB per block, 15 us of copy + 2.5 us of sync + 20-48 us of waiting,
       0.04-0.14 s per read.
   Saving: 0.23 s (0.16-0.31).
     - About 0.05 s more from the indexer q_b, but about 0 once lever 4's H16 form exists.
     - Splitting the router or compressor rows nets about 0, because each needs its own pull.
     - With E in place, the new pull hides too: +0.05-0.1 s.
   Effort: M-L. A third pull per layer, arena pointers for every q_a / kv reader, and new strides at the norm,
   StatePack and publish sites (pcd README item D).
   Bit-exact risk: none. Every row is still computed whole on one card, and the pull copies bits.

6. Dense Q8_0 forms past the x-port cap
   Time now:
     - About 1.2 s of Q8 dense rows, at 0.30-0.35 ps per multiply-add.
     - So the 64-token Q8 forms are about 1.25x the x-port bound, not 2x the FP32 floor as the raw ratio suggests.
   Floor:
     - FP32: 0.174 ps.
     - x port with 2-row tiles: 0.242 ps.
     - With 4 rows x 8 tokens per tile: 0.218 ps (ALU-bound).
   Saving: 0.08 s (0.03-0.15).
     - R=4 x T=8 needs about 80 registers per lane, which means the 256-register mode and half the threads.
     - The existing T=4, R=4 forms run at 0.35 ps.
   Effort: M. Bit-exact risk: low, if each lane keeps its column order and butterfly.

7. Parallel expert grouping (ExpertGroupM)
   Time now: 0.098 s at 64 (47 us per launch, 72x a launch), and 336 us per launch at 256.
   Floor: about 10 us per launch, a counting sort of 384-1,536 slots.
   Saving: 0.08 s at 64. The 256 part is counted in lever 2.
   Effort: S. Bit-exact risk: none. Groups only decide which slots share a decode; each output and the combine's
   slot order stay the same.

8. 12 / 8 head imbalance in prompt blocks
   Head layout:
     - Prompt blocks of 16 tokens or more use 12,12,12,12,8,8 heads (OWN_TP_HEADS 3,3,3,3,2,2).
     - No card holds 16 heads in a prompt block; 8,8,16,8,8,16 is the one-token layout.
     - Both profiled cards, 0 and 2, hold 12.
   Clocks:
     - Card 0 (a 275 W card) computes 6 % faster than card 2 (a 230 W card) and waits that time away in the
       exchanges. So the pace is set by the 12-head 230 W cards.
   Time now:
     - The 12-head cards carry about 133 us per layer more (q_b, attention, o_a, pair swap).
     - The 8-head cards take about 32 us more of the mix dots.
     - Net, cards 4 and 5 have about 0.21 s of slack per read.
   Saving: 0.06 s (0.02-0.12). Moving about 1/3 of the slack off the four heavy cards, by giving cards 4 / 5 more
   dots or using an 11,11,11,11,10,10 layout. Free first test: OWN_MT_DSPLIT_WA=0,0,0,0,1,1.
   Effort: S for the runtime weights, M for the layout. Bit-exact risk: none, as long as every head stays whole on
   one card.

CLOSED
  - Two blocks pipelined across card groups (cards 0-2 on layers 0-19, cards 3-5 on 20-39).
      - It needs a weight layout different from decode.
      - That means a second copy (28 GB per card against 3.45-3.98 GiB free) or a 28.7 s re-upload.
      - Its gain, hiding exchanges, is what E gets in place.
  - Fewer exchange bytes.
      - The bytes are fixed by the bit-exact layout.
      - Column-split down needs cross-card partial sums, which change the order.
      - Expert parallel moves 7 x 5,120 floats per token instead of 7 x 2,304.
  - Clock-aware row weights: at most 0.08 s, and the 16-row granularity loses the gate/up part.
  - Power caps: if the four 230 W cards ran like the 275 W ones, about 0.33 s would come off. That is an owner
    hardware decision, not a software lever.

TOP THREE
  1. E, exchanges overlapped: 0.62 s (0.43-0.84). Scheduling, large, low risk to bits.
  2. Blocks of 256 done right: 0.44 s (0.30-0.50). Mostly the form table plus two kernels, medium, no risk.
  3. Expert kernels rux-2: 0.40 s (0.31-0.64). Kernel, medium-large, low risk, low confidence.
  Cheapest per second saved: lever 4's H16 form (0.14 s, small) and lever 7's grouping kernel (0.08 s, small).

STILL TO MEASURE (GPU, main thread)
  - A prompt-block timeline, to split copy from wait in the exchanges and set E's ceiling.
  - A card 4 profile on tp97, for the 8-head cards' real slack.
  - An IGC dump of the tp97 Q6 forms.
