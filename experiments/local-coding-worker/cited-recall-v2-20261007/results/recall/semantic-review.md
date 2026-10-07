# Fresh v2 recall: independent semantic review

**Full semantic gate failed: 12/30 complete criteria, 0/10 fully covered questions.** All ten answers completed, all 20 citations are relevant, and all 20 mechanically compiled quotations exactly match the frozen lines. No listed disqualifying error was observed. This is incomplete coverage, not a claim that the remaining statements are false.

The dominant issue is omitted conditions: 15 failed criteria have partial correct coverage and three are absent. The answer omits the CPU-only evidence limit for loop feedback, full public-asset re-verification, and exact external-mount admission. Other gaps include the total/output capacity numbers, acceptance hash receipt, full isolation controls, bounded fault recovery, and timing definitions. Citation text containing those details does not count as stating them in the answer.

| Question | Complete criteria | Main missing content |
| --- | ---: | --- |
| V2Q01 | 1/3 | Authorized bounded reuse/graceful stop; actual availability checks |
| V2Q02 | 0/3 | Original successes versus held-out failures; loop evidence boundary; separate agent/human review |
| V2Q03 | 1/3 | Acceptance hash receipt; credentials, read-only root and resource bounds |
| V2Q04 | 2/3 | 33,024 total context including output and 2,048 original output cap |
| V2Q05 | 1/3 | Reject incomplete results; quality/determinism gates |
| V2Q06 | 2/3 | Pristine public source and exact hash-bound dependency closure |
| V2Q07 | 2/3 | Download/re-hash every public asset and binary/checksum checks |
| V2Q08 | 1/3 | Peak writes, actual filesystem/floor, exact mount and historical-advice limits |
| V2Q09 | 1/3 | Fresh admission conditions; drain, graceful stop and bounded-probe sequence |
| V2Q10 | 1/3 | result.json/hash roles and distinct timing definitions |

V2Q02 makes human approval a mandatory condition beyond what its cited ranges state; V2Q05 similarly specifies human review where the cited source says review. These are conservative but over-specific attributions, not listed disqualifiers. V2Q09 uses three sentences despite the one-or-two-sentence instruction. The JSON/quotation gate does not test that prose instruction.

One request finished naturally with 10,135 input tokens, 1,643 output tokens, explicit zero cached tokens, and 176.26 seconds of request elapsed time. It did not exhaust the 3,072-token output cap or timeout. The result supports bounded source lookup with relevant references; it does not establish complete operational recall, unattended coding capability, a controlled before/after improvement, or runtime qualification. Dense compound criteria and a short-answer instruction are a design tension to address only in a future fresh evaluation.

All 30 criterion judgements, all 20 citation assessments, every disqualifier, and hashes binding the original response/SSE, prompt, protocol, profile, corpus, rubric and runner are recorded in `semantic-review.json`. Original artifacts remain unchanged; no repair, rerun, model request or source edit was performed.
