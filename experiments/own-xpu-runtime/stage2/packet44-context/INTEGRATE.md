# Integrating packet44 with packet40

The table below is the complete changed-file list against the copy recorded in
baseline.json. integration-delta.json carries both hashes. New packet44 review,
gate and documentation files are local additions, not edits to packet38.

Keep packet40 fixture retention, cancellation and nonblocking draft work. Merge
packet44's launch extent into Engine and draft state: refresh only QSA selection
and attention, swap extent with the alternate bank, and admit each position
before issuing work. Preserve packet40 cancellation checks while refreshing.
Keep its reset/terminal-state semantics and add both extent fields to the state
inventory. Capacity does not authorize prompt/KV reuse across requests.

Adapter Shape/Spec gains extent. Zero means capacity for legacy callers. New
launch sites pass the rounded valid bound only for selection and attention.
Do not change valid-position reduction leaves, pooling groups or tie order.
The full RoPE table preserves every old byte. Reconcile packet40 draft fixture
retention with packet44's valid-prefix row dumps; final state remains complete.

Merge wrapper safety fixes once, preserving unchanged LD_LIBRARY_PATH and
structured owner-failure evidence. Both suite caps come from their manifest;
context is separately checked against it. Regenerate all merged receipts and
rerun CPU qualification. Neither packet's receipts qualify a different merged
binary. Device windows are pending and must be rerun after integration.

| Changed copied file | Base SHA-256 | Packet44 SHA-256 |
| --- | --- | --- |
| adapter.cpp | 1c754cbd5775e463660e37b05330743d34fb552fda68aa193b4df1a8f7c3f882 | 031609948a0bc912e127ca56428577e2f882b86a5f6e1b0526e8a9adf8bf5ff6 |
| adapter_fixture.cpp | c992799b4d65254620c2baab0ffe953c7d165268d03e9e9508dc184753eea1cf | 8b72f5892f11bdea401964b76ddd640e0cc1e60bfd8bcb56ed19fd0eec5104a8 |
| build.py | 107e24ace921d984b7bdb0e90855bbc7d7f4e9c7136a1afe73d24ed8a9c56806 | 8274efd8b12869fc9c7ffa1c19e5a561b1b1597fc28672ddd60491fe9603b860 |
| capture_gate.py | d7ffe159910c16d0987b2e5628f8a47872eb1f543718dc6a9c5a898bbef1580a | 11bd9bd9d10814c5e565696af13db63a82234d059ef81ffe6ba90f6c71f42334 |
| draft_window.py | 452d4ff4a02f81f5a59203d0f02572235cf60bfba6409e7507a041eadd939c9d | 0fad1a3a5f0a21bc54aad838585eadc46d27e66a52da65d681ac75c406c4591c |
| fixture_driver.cpp | 321f790cece417bd2ab8afa9e01f6d16c2a26c32d5000be448635515cb9556fb | 139123d27d61582e8d2f6dd443cacc7d12337d79a600d44063489d87f30a9fd1 |
| fixture_support.py | 00c1bbbf9d41901bd084d34bc9e127e6a52757af2b76468093f1b8b7202731ce | e6ce81fc08bc32862ed88dee24131dccd92cd11e6101834714d3a099877aa0e4 |
| integration_inventory.py | 8ae47f962b5b82db13164597435f62dca898dc907f733b53e8fce1edd78481e0 | 80474411a6182512c48a114bad7140eda3831515bc7220b9c49a267a69850cd9 |
| k2_summary.py | 774880bc33dcc0f5134bb1173f45140c38264458ea11e549da30335ee7a01bf7 | caf95768673ae391d4bc26a930f9086e49bd4d2f03695da97b42e39012d8915d |
| kernels.hpp | 24e24e660203c959db09d30dc633490906508b749cf4e2838e2df50d4013d43a | a8c19f5ccf8dec343f70ca14223d5ac52df42c8c3ae68072179f61e285e17466 |
| main.cpp | d409f9ab0f096338c3a0a93f547d635d04eac7339f6c9f50cd17b350b0259251 | ba06d8010554bca23463c9acade6872e603d279b7253adf7fdd60611137472d5 |
| memory_gate.py | d9efa96d6cbcfe67bbaafecfd753bd598d149b3430fc068b8e07485a97965350 | 68481c0c90c802e2a2a3295d98cd2eca9a0985f9052b4708ab19aa234a623b50 |
| mtp.hpp | dbef887e12fe8d1e398a83e5a6a8dbdb7bc29dbabd803a25d2870c974552845d | cdf088f333b9fb52da1e3b509676676c824d83435edc7615b83e4f7b6b50307a |
| p30_attention.cpp | d72c76a532192487986b808f34232c96b41fd94c39511978b2c8c945a192285c | 72403adc474cad4c112e59b2f2ffbff7fe0e52dba2874a36feb8c41df829e815 |
| p30_attention.hpp | b5c55ae4545c7273e84b1aa7aa345de1fb52605d53b7246fbd4f9985e275d618 | 9d5eb89f4aa6515922a74b144a4bc3d19813169261f1cb1bb2ce6bf042608ddf |
| p30_submit.cpp | a9760c71db9a438c81ce6b3e42ccd936e37585c934c7a48da817396615fad70d | dab72a991d33df0becdedd69e1e659720ad725465940d704d3badb15c689449f |
| p33_candidate_cpu.cpp | 648e43a52d503a62af85640c756db9fe95525b7d526a5f8f99c8612f6a6517e0 | 711b730573ef4d600108cc455f79dabdfbdb557f3c57a4df64171e010ad2d53f |
| pipeline.py | f1b6affa69c2275754281d6f278bf47a17fa7a004c4029b71bcea37b98111800 | a2c7f11bde5877df1234581fdafc9ade9b29fe4ea423ead5c7cbc3f334ff4d34 |
| prototype/snapshot/kernels.hpp | 22bf27fc4d3175c88549e8ccb4cc25d4c2626754660b1038bfceafd48ff15155 | 804c720eb7339e1d90c786ca43c8399fbe52999dd668ea43c30ad7a559a677f1 |
| prototype/snapshot/reference.hpp | 9dbd20b4d8b210be469e1a8dc31c1592b18d352f15c3bee7058c18bf9aa924bc | 41ff760abf1a4f7234f02ee209e232f4be2071273a3c703935472350a4db668b |
| rank.hpp | 668c402ca38175ee77f7388f4f5b711709923eb29ba639df5f51b4255bae1274 | 37a9e7ad4b2ce7559c39c9beeac5ea3a8c08ebcd49ac97f20e38cfe518dd353a |
| request_state_inventory.hpp | c4818d42606ec5f29e00c7fa0ede2f12b4bdc6c6c2f5ca1740ca5e9cc023ea65 | 1341737c1005f0bf7ae216648c4ee29805d5e3efa384184ee76e98521a275902 |
| rope.bf16 | ccdfe87fa7360fc6b4aa7c999fa7b920f791f5635010cf303ae76f4d01dca058 | 92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390 |
| rope.hpp | 93d877610f8db3ebcd7b4d7d16c2e3968d78ee291e3609ba460f1dc325cbb885 | 83782198e96337883f7e226d5fc474360841f6ca26a00bce43a6d87f42b74929 |
| round2.hpp | 5b3ddd9ba04b8a9b8fc6953ef6d47ac275a97af0bf8f7b95e8d95a89a6203f83 | bd614a9944e33903a6f0c7c2d4a1dd1de4786f8b1cdc8418df73e6d54b7e38ef |
| runtime_kernels.hpp | ab201fd52d9cfdd33b1f2fa9f5648bd13dc5af1ab0f82986fd11a82e7ba00cdc | 49e2a958a36a087b379b2e85d90ee34c63817659b31c617ced9e5854f7774501 |
| specialised.hpp | a5604dcf33c1f01940505b3ab5e6fab8d05e9f6ba6fed2884f40ae95b47c88cb | 0d7489d31fb869a49db3a7a365dbe78af52931c0e7d5cdf38ff05b01e594c126 |
| suite.py | 43401ba3f5b40a5a1a8c4ebfd341ee6b97e818270ef76f2f4464785c90425ea6 | 2a9a5c1cf4e7a57f6c5b5a68997c7133d7c9954c3edc52b1519ed226b04d054e |
| test_window.py | 7ec70cc8552ae8ec32e6361dec23ea498127b66ad3af4b7a6e627619bdb63f6c | cb05ab154b11d516a763bd054fdbc6ced0aac030a963c04e42d5acc30e3c29ee |
| test_window_seal_admission.py | 0314333ff27ef80005f67e8afd2b4e96cf76d6ca3a5a7c845a4755b4fab6db9f | ab26efc28f2b0c9542c4a8645adf04b32fdfd74418c0bc84afad17e94ff4dd95 |
| test_window_storage.py | 86001852f3d91eb0afde1698e2a29d5962c6b5109e54a5e4347a8fcaaa7276e5 | ee3f366a8ccc8bf9336721c716a38b0110ab8a3fbc334315941bed834cdd5b1a |
| window.py | 0ffd70228f1bddc6a932fd9655dea6eb10112612fd3747e66995faf37db7ddb0 | 67b024be6bba40deb319a53df0574298c0a13138a4a3115afa3f89d5f1c87548 |
| window_safety.py | 735d64f9c6cbbb605c414bc87fe7042f909efae126f323974b2365132794057b | 353ce418d0570d3b85d23dc63dc91f7e005e528e91057d7a7ee620d390d02264 |

The complete new-file list (including every evidence artifact) is the `added_files` array in [integration-delta.json](integration-delta.json). New source/helpers are:

- `capacity_cpu_gate.py`
- `capacity_draft_gate.py`
- `capacity_fixture_gate.py`
- `capacity_rollback_asan.py`
- `capacity_selection_gate.cpp`
- `capacity_selection_gate.py`
- `cleanup_objects.py`
- `context_window_gate.py`
- `draft_baseline.py`
- `final_build.py`
- `finalize_docs.py`
- `finish_cpu_gates.py`
- `generate_rope.py`
- `memory_plan.py`
- `post_python_gates.py`
- `remaining_cpu_gates.py`
- `resume_draft_references.py`
- `resume_intel_composite.py`
- `run_native_gates.py`
- `seal_context.py`
