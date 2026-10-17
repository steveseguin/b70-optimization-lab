# Packet75 submission

`submission_cli.py` retains packet70's registered-chain or pinned-resume
validation. Only a complete packet75 chain can produce a payload. The frozen
packet49 oracle remains authoritative; record comparison uses the current
monotonic threshold file, currently54.162021859952475tok/s.

Notes disclose all inherited and selected changes and are limited to2000
characters. Packed target weights retain exact dequantization and the existing
expanded draft prefix; HC and expert load scheduling choices are named and
explained. Full BF16 KV and unchanged target verification are explicit.
Resumed runs disclose imported hash-bound early receipts.

Preparation does not submit, validate against an external API, or read secrets.
Use `python3 -B <packet>/submission_cli.py --help` for the retained interface.
The strict512-token gate stays false; the inherited named128-token exception
and all independent quality gates remain required.
