# Multi-user result: the two-card 27B serves 16 users at once losslessly, 423 tok/s together (2026-10-04)

## In plain words

Until tonight the Qwen 27B recipes were measured for one user at a time: about 90 tokens a second on two cards.
We had never measured several users at once on this model. **With speculation switched off, sixteen users at once
each get exactly the answer they would have got alone, and together they get 423 tokens a second, 4.7 times the
single-user rate.** The answers are the same ones the published single-user recipe gives, token for token. Past
sixteen users a few answers start to differ, so sixteen is where the lossless mode stops.

Speculation is what makes one user fast (90 instead of 34), but as shipped it is not lossless once two requests
share the server. The image carries a set of switches that make it lossless under load; with them, speculation is
exact through sixteen users, but it is slower than simply switching speculation off at eight users or more, and it
makes a single user slower (75 instead of 90). So the simple mode wins.

## Numbers

Two cards, the shipped image, 64 prompts with 128-token answers, all sent at once to a server that runs N of them
together, two passes. "Lossless" means all 64 answers equal the one-at-a-time answers in both passes.
[Preregistration and addenda](2026-10-04-fp8-multiuser-prereg.md); receipts in
[`../data/2026-10-04-fp8-multiuser/`](../data/2026-10-04-fp8-multiuser/).

**Shipped arithmetic** (reference: the frozen single-user no-speculation answers the package is gated on):

| Mode | Users at once | Equal to solo, pass 1 / 2 | Tokens a second together | Per user | Lossless |
| --- | ---: | --- | ---: | ---: | --- |
| depth-5 speculation (the shipped recipe) | 1 | 12/12 strict, 64/64 ladder | 90.3 | 90.3 | **yes** |
| no speculation | 1 | reference | 33.9 | 33.9 | yes |
| no speculation | 8 | 64/64, 64/64 | 237 | 29.6 | **yes** |
| no speculation | 16 | 64/64, 64/64 | **423** | 26.5 | **yes** |
| no speculation | 32 | 60/64, 58/64 | 656-676 | 21 | no |
| no speculation | 64 | 61/64, 58/64 | 876-917 | 14 | no |
| depth-5 speculation | 2 | 60/64, 61/64 | 136-140 | 69 | no |
| depth-5 speculation | 4 | 61/64, 61/64 | 227-239 | 58 | no |
| depth-5 speculation | 8 | 57/64, 61/64 | 335-363 | 44 | no |

The misses are the same few prompts every time (`cache-c040`, `evidence-c047`, `rollback-c010`, `cache-c000` token
96 and a handful more): exact logit ties that fall the other way when the batch shape changes, the mechanism found
in September.

**Batch-invariant switch set** (packed-serial FP8 linear, serial-exact GDN speculation, serial verify attention,
batch-invariant LM head and RMSNorm, FP16 class pad). It rounds in a different order, so it has its own reference
(its own one-at-a-time no-speculation answers), which differs from the shipped one on 3 of 12 strict prompts:

| Mode | Users | Equal to this arithmetic's reference | Together | Per user |
| --- | ---: | --- | ---: | ---: |
| depth-5 speculation | 1 | strict 12/12 twice, ladder 64/64 x3 | 74.9 | 74.9 |
| depth-5 speculation | 4 | 64/64, 64/64 vs its own solo | 163-169 | 42 |
| depth-5 speculation | 8 | 64/64, 64/64 | 227-237 | 29 |
| depth-5 speculation | 16 | 64/64, 64/64 | 268-279 | 17 |
| no speculation | 64 | 54/64, 54/64 | 857-865 | 13 |

So speculation **can** be made lossless under load on this image, through sixteen users. It beats the plain mode
only at two to four users (about 165 against 125 together at four) and loses to it from eight users up; it also
costs a single user 17 %. It does not make sixty-four users exact.

## One card

Same check on one card (shipped image, no speculation, 24,576-token context, 896-token attention block), against the
frozen one-card no-speculation reference the one-card package is gated on:

| Users at once | Equal to solo, pass 1 / 2 | Equal to the frozen reference | Together | Per user |
| ---: | --- | --- | ---: | ---: |
| 1 (shipped recipe, depth-5 speculation) | 12/12 strict | yes | 54.0 | 54.0 |
| 8 | 64/64, 64/64 | yes | 137 | 17.1 |
| 16 | 64/64, 64/64 | yes | **245** | 15.3 |

One card has far less room for conversations than two: its shared context pool is about 52,000 tokens in this
configuration, against about 400,000 on two cards. Sixteen users on one card means about 3,000 tokens each.

## What this means for the recipe

- **One user: the shipped recipe, 90 tok/s.** Unchanged.
- **Several users: a second profile, speculation off, up to sixteen sequences.** Same image, same arithmetic, the
  same reference answers as the single-user recipe. 237 tok/s together at eight users, 423 at sixteen; each user
  sees 26 to 30 tok/s.
- The two cannot be one server: speculation has to be off for the multi-user mode to be lossless, and that costs a
  lone user two thirds of their speed.
- The batch-invariant speculation mode is recorded, not recommended: narrower win, different reference, slower solo.

Nothing here is published as a package profile yet. A profile needs its own acceptance through the package
launcher, and editing the launcher moves bytes the frozen acceptance packet pins.

## Not established

- More than 128-token answers, long prompts, and mixed prefill-and-decode load at sixteen users (the 64-prompt
  ladder is short-context). The September work found a mixed-step effect in the GDN kernel that `GDN_SPLIT_MIXED=1`
  (shipped) handles; it should be re-checked at this width with long prompts.
- Where between 16 and 32 the lossless boundary sits, and whether it is the same on every boot.
