# ctxkeeper 1.2.0 — draft

Keep an agent working beyond its model’s context window. ctxkeeper is an OpenAI-compatible proxy with
editable notes, a searchable verbatim archive and a recall tool. Python 3.10+, standard library only.

This release fixes failures found in recorded two-million-token conversations: item-prefixed changes no
longer create stray names; full rewrites retain untouched state; list-like records avoid spurious partial
checks; and nonnumeric remarks cannot silently replace numeric state. Optional archived-entry lookups,
cited entries, rule scans, open-question reminders, item boundaries and arithmetic checks improve handling
of old corrections and standing rules. These options are documented individually and remain off by default.

Verified on both two-million-token hostile seeds (lab campaign 49, hash-bound public audits): 421/423 and
417/423, all 16 corrections applied on both seeds; every forged line the notes carried was flagged, and no
forged value, method, rule or removal was ever adopted. Two of 97 forgery-target answers slipped on silent
arithmetic while the notes held the right value, so the lab's strictest preregistered bar is not claimed.
The release-installation gate (campaign 50) is pending. Memory can still be wrong; this is not a guarantee
of perfect recall or security against arbitrary hostile content.

Before publishing this draft, fill in the gate results, public installation checks, asset checksums,
download page and exact release URLs. Do not claim unpublished gates passed.
