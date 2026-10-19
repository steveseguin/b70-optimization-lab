# Packet58ap exclusions

- Do not modify or recompile the parent demand runtime to make this chain pass.
  The exact executable and sources are vendored. A different v5 binary refuses.
- Do not substitute packet58aj's -0.5% non-inferiority rule. This packet requires
  >=+0.5% over every warm control, all exact and <=3% drift.
- Do not count A0 in speed/drift or exclude it from exactness.
- Do not mistake the inherited single-view CPU probe for demand execution.
  Its internal branch selects off; the additional five-view CPU reset probe
  is required and explicitly separate from the actual chain argv.
- Do not reuse `card0-58ap-a`, retry a failed chain, profile the timed windows,
  label synthetic streams as measurements, or claim strict512 from 128 tokens.
- Do not emit old packet58aj smoke proposals from this packet. It prepares only
  the new record chain; the coordinator owns packet58am's smoke and v5.
