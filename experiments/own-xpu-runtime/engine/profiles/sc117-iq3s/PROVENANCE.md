# SC117 immutable profile provenance

These repository records supplied the profile, descriptor tables, tokenizer/template and launch policy. Generation read retained metadata only; it did not rehash model files. The deployment preparer must authenticate actual full files before generating local authority. Stat/device/inode/timestamp fields from historical records were excluded from the portable profile.

| Retained source | SHA256 |
| --- | --- |
| [gsq-rco-iq3s/model-identity.json](../../../gsq-rco-iq3s/model-identity.json) | `a3b1e65332dc5dc8fe53a9feea4e97468b4995ff7eeb2f0a0cd75904199c881b` |
| [gsq-rco-iq3s/loader/placement.tsv](../../../gsq-rco-iq3s/loader/placement.tsv) | `a9ab0302d85f208717748c70be9d09d0a494e07f494a0e67b39dac6cc9468253` |
| [gsq-rco-iq3s/metadata/new-census.json](../../../gsq-rco-iq3s/metadata/new-census.json) | `b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1` |
| [gsq-rco-iq3s/mtp/draft-manifest.tsv](../../../gsq-rco-iq3s/mtp/draft-manifest.tsv) | `eb9d805e5b24b3918196b628eafb1fb9c40f9d3d835fb10b521e5b3950d2ecc9` |
| [stage2/packet1/tensor-contract.json](../../../stage2/packet1/tensor-contract.json) | `37daac926403b543bd5e1d6db06e70487feebd8ef97880d106e58f91011b5c96` |
| [gsq-rco-iq3s/coverage/tokenizer.py](../../../gsq-rco-iq3s/coverage/tokenizer.py) | `c22937e549718f68c7892e188f05fcff581343677207484782d506f50935f6ab` |
| [gsq-rco-iq3s/serving/lan/dispatch-f32-select-gdn2.json](../../../gsq-rco-iq3s/serving/lan/dispatch-f32-select-gdn2.json) | `d0705c52ca12347632b4d67fef6abdc6145abe41d327e8449eefcdd5b666654d` |
| [research/review-2026-10-25/pp-proof/pp2/plan.json](../../../research/review-2026-10-25/pp-proof/pp2/plan.json) | `c9009f238d5b40d4ebab44ce52f06287828d74a17a4060d9b5baa88afc5d8ea6` |

Target placement offsets are **relative to each GGUF payload base**, not absolute file offsets. Each target shard profile therefore records both authenticated header bytes and `data_start`. Draft tensor offsets are absolute safetensor file offsets. Target headers/full-file hashes bind the actual GGUF metadata; the compiled expected descriptors remain separate from candidate data.

The draft manifest retains its first eight immutable columns (tensor, shard, offset, size, dtype, rows, columns, payload SHA256). Full draft shard hashes/sizes come from the official tensor contract. The generated local draft manifest restores verified local stat columns only after full shard and individual payload authentication.

The text template is the exact UTF-8 value retained in the target metadata census. `profile.json` hashes its raw bytes, while the historical census additionally retains its canonical-JSON hash. No template was inferred or modified.

The launch policy retains the measured PP proof dispatch and numerical flags. It is separate from immutable model identity. Its paths, GPU BDFs and dynamic-loader directories come from explicit local inputs. Profile preparation and plan generation alone establish neither runtime admission nor quality/performance certification.
