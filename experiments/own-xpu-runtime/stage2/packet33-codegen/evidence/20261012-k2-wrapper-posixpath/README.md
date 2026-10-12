# K2 wrapper stopped before launch: a path object in the recorded command (2026-10-12 01:51:37 UTC)

The coordinator ran K0 (passed, card 2, 01:45:10–01:46:08 UTC) and then K2 exactly as
WINDOW.md says. `window.py` raised `TypeError: Object of type PosixPath is not JSON
serializable` in its first `persist()`: the K2 command list ended with a `Path` for the
fixture directory. The native program was never started; no device was contacted; the
kernel log is unaffected. The empty `build/k2-card2/` directory it had already created is
left in place (ignored build output).

Fix by the coordinator: one `str()` in `window.py`; the source seal entry for `window.py`
in `build-receipt.json` was updated and the change recorded there under
`coordinator_amendments`. No native binary, kernel source or gate changed. The rerun
uses the new output name `build/k2-card2b`.
