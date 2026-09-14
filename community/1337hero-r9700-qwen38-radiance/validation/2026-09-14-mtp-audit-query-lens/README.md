# Inactive GDN metadata subtraction candidate

This two-line relocation targets the qualified R304 FP8/MTP1 source. It is **not installed**, has no GPU test or speed result, and is not a recommended runtime change yet.

The current builder computes GPU `query_lens` on every speculative step. All four reads occur only in the mixed branch. Moving the same subtraction immediately before those reads skips one GPU integer subtraction on an all-spec step. It preserves the R303 first-chunk classifier and R304 active-width logic, and changes no target arithmetic, draft depth, KV precision or verification rule.

[Patch](candidate.patch) and [source proof](proof.json) bind the original and candidate hashes. The original hash matches the frozen R304 contract and the served source copy. Checks confirm that the entire AST difference is one assignment move, all variable uses stay in the mixed branch, no crossed statement references the GPU source tensor, zero-fuzz patch replay reproduces the candidate, and syntax compiles without importing or executing the module. These checks do not establish runtime alias/lifetime safety or output identity.

The idea is acknowledged to magiccodingman's Radiance metadata review: [lines 24–25](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_gdn_metadata.py#L24-L25) describe this deferral. The pinned patch's actual replacement still computes the subtraction eagerly; this focused R304 adaptation is lab follow-up, with **no validated boost**.

Before any future integration, test native metadata equality and state lifetimes, complete qualified FP8/MTP1 outputs at short and longer contexts, and matched timing and health. The historical image is the reproduction anchor; active runtime development must still follow the repository's current-upstream policy. Do not use this source-only candidate as a reason to interrupt the restored service.
