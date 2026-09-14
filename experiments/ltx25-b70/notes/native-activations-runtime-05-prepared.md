# Native activations packet05 preparation

2026-09-14. `prepare-native-activations-runtime.py` prepared a separate immutable
`prepared-encoder-compiler-05` from packet04. Preparation performed no native
imports, device discovery, server operations, or edits to packet04. Runtime
admission/deployment and subsequent numerical results belong to the owning
campaign and `CURRENT.md`; this note records source preparation only.

The effective adapter changes exactly two expressions: import `make_backend`
from `ltx_native_activations_backend`, and write its graph receipts under
`native-activation-graphs`. The unchanged compiler invocation binds original
OPTIONS, `fullgraph=True`, `dynamic=False`, and15 RMS replacements. The new
backend's pinned defaults additionally require six sigmoid and two explicit
tanh-GELU replacements. RMS uses the unchanged pinned dependency. This is a
separate hypothesis after the RMS-only native block failed, not a claimed fix
or qualified speedup.

Required identity changes affect the adapter hash literal in both compiler-node
copies and the packet-local checker/manifest extension inventory. All original
node/lifecycle/registration checks, OPTIONS, launcher bytes, server flags,
graphs, model sources, decoder and loader sources are unchanged. No NA extent
or loader-memory patch is included.

Source gates passed: the whole adapter AST reverses exactly to04 after only the
two declared substitutions; both node copies differ only in the adapter hash;
the checker reverses exactly to04 after its explicit identity/ancestry additions.
All1247 inventoried files passed the new checker, including ancestry through
RMS04, compiler03, and encoder03. Original changed files and parent manifests
are preserved in provenance. The RMS04 metadata remains historical dependency
provenance; `native_activations` describes the current backend and receipt path.

The copied launcher also passed `--check-only` using the pinned venv and proposed
`encoder-server-compiler-05` directory. That operation performs no device
discovery, locks, run-directory creation, or GPU work. Root owns the single
application replacement and the separately reviewed v4 client.

- Packet manifest SHA256: `45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5`
- Parent04 manifest SHA256: `c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9`
- Adapter SHA256: `c3f3e4ede85b2798981dca40562bd77586ad63afe55b043c0705fceddda29a1e`
- Activation backend SHA256: `62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a`
- Unchanged RMS SHA256: `09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb`
- Builder SHA256: `cfbdb1c7aa7eeb34b50e610f0390c7463fc8b00b7044f6acaa620267e65f4f24`

Tracked evidence: `data/native-activations-runtime-05-preparation.json`,
`data/native-activations-runtime-05-manifest.json`,
`data/native-activations-runtime-05-source-checks.json`, and
`data/native-activations-runtime-05-startup-check.json`. The four inherited-file
changes are in `patches/native-activations-backend-runtime-05.patch`; the added
backend is separately pinned above and copied into the packet. Both original
builders and packet04 remain unchanged. No commit was made by the preparer.
