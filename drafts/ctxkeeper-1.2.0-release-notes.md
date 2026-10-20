# ctxkeeper 1.2.0 — draft

Keep an agent working beyond its model’s context window. ctxkeeper is an OpenAI-compatible proxy with
editable notes, a searchable verbatim archive and a recall tool. Python 3.10+, standard library only.

This release fixes failures found in recorded two-million-token conversations: item-prefixed changes no
longer create stray names; full rewrites retain untouched state; list-like records avoid spurious partial
checks; and nonnumeric remarks cannot silently replace numeric state. Optional archived-entry lookups,
cited entries, rule scans, open-question reminders, item boundaries and arithmetic checks improve handling
of old corrections and standing rules. These options are documented individually and remain off by default.

Verified development result: seed 0 scored 421/423, preserved every forgery target and applied all 16
corrections. The matching second seed and release-installation gate are pending. Memory can still be
wrong; this is not a guarantee of perfect recall or security against arbitrary hostile content.

Before publishing this draft, fill in the final results, public installation checks, asset checksums,
download page and exact release URLs. Do not claim unpublished gates passed.
