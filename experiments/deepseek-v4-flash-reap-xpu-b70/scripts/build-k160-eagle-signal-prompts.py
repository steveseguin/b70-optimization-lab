#!/usr/bin/env python3
"""Build deterministic, procedural, non-frozen K160 EAGLE train/DEV prompts."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

CATEGORY_SHARES = {
    "prose": 0.45,
    "code": 0.15,
    "math": 0.15,
    "extraction": 0.15,
    "low-locality": 0.10,
}

NAMES = [
    "Amina", "Bastien", "Chao", "Daria", "Eleni", "Farid", "Greta",
    "Hiro", "Imani", "Jonas", "Kavya", "Luca", "Marta", "Nabil",
    "Olena", "Pavel", "Rina", "Soren", "Tala", "Vikram",
]
PLACES = [
    "a coastal observatory", "a winter market", "an archive below city hall",
    "a remote field station", "a neighborhood repair cafe", "a night train",
    "a desert greenhouse", "a public radio studio", "an island ferry terminal",
    "a university machine shop", "a mountain clinic", "a riverside warehouse",
]
TOPICS = [
    "water allocation", "restoring an old map", "a disputed translation",
    "community-owned energy", "an unreliable sensor", "a missing ledger",
    "seasonal migration", "a difficult apprenticeship", "public memory",
    "an unexpected scientific result", "food preservation", "urban tree cover",
]
TONES = [
    "restrained and observant", "warm but unsentimental", "tense and precise",
    "wry and conversational", "lyrical without becoming ornate",
    "analytical with vivid concrete detail",
]
LANGUAGES = ["English", "French", "Spanish", "German", "Portuguese"]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def random_words(rng: random.Random, count: int) -> list[str]:
    syllables = [
        "amber", "birch", "cobalt", "delta", "ember", "flint", "grove",
        "harbor", "iris", "juniper", "kepler", "linen", "morrow", "north",
        "opal", "prairie", "quartz", "river", "sable", "tundra", "umber",
        "violet", "willow", "xenon", "yellow", "zephyr",
    ]
    return [f"{rng.choice(syllables)}{rng.randrange(10, 9999)}" for _ in range(count)]


def prose_prompt(rng: random.Random, index: int) -> str:
    mode = index % 7
    names = rng.sample(NAMES, 3)
    place, topic, tone = rng.choice(PLACES), rng.choice(TOPICS), rng.choice(TONES)
    if mode == 0:
        return (
            f"Write a long-form scene set in {place}. {names[0]} and {names[1]} "
            f"disagree about {topic}, while {names[2]} notices evidence neither "
            f"has considered. Use a {tone} voice. Continue for substantial length, "
            "developing the disagreement through action and dialogue rather than "
            "summarizing it. Do not add headings or commentary about the prompt."
        )
    if mode == 1:
        notes = "; ".join(random_words(rng, 18))
        return (
            f"Turn these deliberately telegraphic field notes into coherent {tone} "
            f"expository prose about {topic}: {notes}. Preserve every concrete item, "
            "supply plausible transitions, distinguish observation from inference, "
            "and end with two unresolved questions."
        )
    if mode == 2:
        return (
            f"Draft an extended dialogue in {rng.choice(LANGUAGES)} between "
            f"{names[0]}, an experienced practitioner, and {names[1]}, a skeptical "
            f"newcomer, about {topic} at {place}. Let each speaker revise one belief. "
            f"The tone should be {tone}; avoid generic motivational language."
        )
    if mode == 3:
        return (
            f"Write a detailed magazine-style explanation of {topic} for an informed "
            f"general reader. Open with {names[0]} at {place}, then move between the "
            "concrete case, historical background, competing interpretations, and "
            f"practical consequences. Keep the prose {tone}."
        )
    if mode == 4:
        fragments = " | ".join(random_words(rng, 24))
        return (
            f"Edit the following fragments into a polished reflective essay without "
            f"dropping any fragment: {fragments}. The essay should concern {topic}, "
            f"use {place} as its recurring setting, and remain {tone}."
        )
    if mode == 5:
        return (
            f"Produce a careful, extended summary-and-critique of a hypothetical book "
            f"called 'The {rng.choice(random_words(rng, 1)).title()} Archive' about "
            f"{topic}. Separate the author's claims, evidence, strongest objection, "
            f"and your final assessment through prose transitions, not headings."
        )
    return (
        f"Continue a literary narrative for at least eight substantial paragraphs. "
        f"At {place}, {names[0]} receives a message concerning {topic}; {names[1]} "
        f"believes it is a trap. Maintain a {tone} style, vary sentence rhythm, and "
        "resolve one local question while leaving the larger problem open."
    )


def code_prompt(rng: random.Random, index: int) -> str:
    language = rng.choice(["Python", "Rust", "Go", "TypeScript", "C++", "Java"])
    n = rng.randrange(17, 250)
    tasks = [
        "an interval index supporting insertion, deletion, and overlap queries",
        "a bounded worker pool with cancellation and deterministic shutdown",
        "a streaming parser for newline-delimited JSON with useful error locations",
        "a small LRU cache whose invariants are checked by property-style tests",
        "a stable topological sort that reports the first concrete cycle",
        "a diff routine for ordered records with duplicate keys",
        "a retry scheduler with jitter, deadlines, and injectable time",
    ]
    return (
        f"Implement {rng.choice(tasks)} in {language}. The primary size parameter is "
        f"approximately {n}. Explain the representation and complexity, include the "
        "complete implementation, and add focused tests for empty input, duplicates, "
        "boundary values, and one adversarial case. Avoid external dependencies."
    )


def math_prompt(rng: random.Random, index: int) -> str:
    a, b, c = rng.randrange(11, 900), rng.randrange(7, 500), rng.randrange(3, 90)
    modes = [
        f"A reservoir starts with {a} units, receives {b} units per day, and loses "
        f"{c}% of its current contents nightly. Derive and solve the recurrence, then "
        "check the limiting behavior.",
        f"Find all integer pairs (x,y) satisfying {a}x - {b}y = {c}. State the "
        "existence condition, parameterize every solution, and verify it.",
        f"A biased random walk moves right with probability {c}/100 on states 0 "
        f"through {a % 40 + 20}. Derive the probability of hitting the upper boundary "
        "before zero and evaluate it for a nontrivial starting state.",
        f"Prove a useful upper bound for the sum from k=1 to n of k^{c % 6 + 2}, "
        f"then evaluate the exact sum for n={a % 80 + 20} and compare the bounds.",
    ]
    return (
        rng.choice(modes)
        + " Show each transformation, identify assumptions, perform an independent "
        "numerical check, and present the final result clearly."
    )


def extraction_prompt(rng: random.Random, index: int) -> str:
    rows = []
    for row in range(rng.randrange(12, 28)):
        rows.append(
            {
                "ticket": f"T-{index:05d}-{row:02d}",
                "owner": rng.choice(NAMES),
                "region": rng.choice(["NE", "SW", "CENTRAL", "COAST", "NORTH"]),
                "priority": rng.choice(["low", "medium", "high", "urgent"]),
                "minutes": rng.randrange(2, 900),
                "tags": rng.sample(random_words(rng, 8), 3),
            }
        )
    return (
        "Transform the records below into a JSON object with keys by region. Within "
        "each region, sort urgent/high items first and then by minutes descending. "
        "Each output item must contain ticket, owner, priority, minutes, and tags; "
        "also include region totals and a global checksum field equal to the sum of "
        "all minutes. Return valid JSON only.\nRECORDS=\n"
        + json.dumps(rows, ensure_ascii=False)
    )


def low_locality_prompt(rng: random.Random, index: int) -> str:
    tokens = random_words(rng, rng.randrange(90, 170))
    permutation = list(range(len(tokens)))
    rng.shuffle(permutation)
    selected = permutation[: rng.randrange(55, 85)]
    return (
        "Using the numbered source list, emit exactly the entries referenced by the "
        "index sequence, in that order. Preserve spelling and digits exactly, place "
        "one entry per line, and add no explanation.\nSOURCE:\n"
        + "\n".join(f"{i}: {token}" for i, token in enumerate(tokens))
        + "\nINDEX_SEQUENCE:\n"
        + ",".join(map(str, selected))
    )


BUILDERS = {
    "prose": prose_prompt,
    "code": code_prompt,
    "math": math_prompt,
    "extraction": extraction_prompt,
    "low-locality": low_locality_prompt,
}


def build_split(split: str, count: int, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    counts = {name: int(count * share) for name, share in CATEGORY_SHARES.items()}
    counts["prose"] += count - sum(counts.values())
    rows = []
    for category, category_count in counts.items():
        for index in range(category_count):
            prompt = BUILDERS[category](rng, index)
            prompt += f"\nImmutable task nonce: {split}-{category}-{index:05d}-{seed}."
            prompt_hash = sha(prompt)
            rows.append(
                {
                    "schema_version": "k160-eagle-procedural-prompt-v1",
                    "split": split,
                    "category": category,
                    "source_id": "k160-eagle-procedural-diverse-v1",
                    "source_revision": "2026-07-19",
                    "prompt_id": f"{split}-{category}-{index:05d}",
                    "prompt_sha256": prompt_hash,
                    "prompt": prompt,
                }
            )
    rng.shuffle(rows)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-count", type=int, default=20000)
    parser.add_argument("--dev-count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=160719)
    args = parser.parse_args()

    train = build_split("train", args.train_count, args.seed)
    dev = build_split("dev", args.dev_count, args.seed + 1)
    train_hashes = {row["prompt_sha256"] for row in train}
    dev_hashes = {row["prompt_sha256"] for row in dev}
    if train_hashes & dev_hashes:
        raise RuntimeError("train and DEV prompt hashes overlap")
    write_jsonl(args.output_dir / "train-prompts.jsonl", train)
    write_jsonl(args.output_dir / "dev-prompts.jsonl", dev)
    manifest = {
        "schema_version": "k160-eagle-prompt-source-manifest-v1",
        "source_id": "k160-eagle-procedural-diverse-v1",
        "source_revision": "2026-07-19",
        "seed": args.seed,
        "category_shares": CATEGORY_SHARES,
        "train_prompt_count": len(train),
        "dev_prompt_count": len(dev),
        "train_prompt_set_sha256": sha("\n".join(sorted(train_hashes))),
        "dev_prompt_set_sha256": sha("\n".join(sorted(dev_hashes))),
        "disjoint": True,
    }
    (args.output_dir / "prompt-source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
