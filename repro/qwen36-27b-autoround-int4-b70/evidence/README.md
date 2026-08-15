# Record evidence

This directory makes review independent of the original `/mnt/fast-ai` paths.

## Promoted extracts

- `strict-realistic512.json`: 12 cold prompts and token-event timing,
  SHA256 `53006eb9f6ce064722fba19cfe133a1f9d6e1f9d6f849b9ec1d9c499661065fd`.
- `summary.json`: promoted run summary,
  SHA256 `681aaa37ba2db64c0bb40aaedeed41da14978ee045fad8af0d736931d0942679`.
- `quality-repeat128.json`: exact, repeat128, baseline, and 1K evidence,
  SHA256 `908557284111f7c3ba59e48f858492534a9a7cdcaf662a442ceaab95c4fe2148`.
- `crossover.json`: both swapped four-GPU windows,
  SHA256 `dd7c4699f09b6e0a3880bf2783af8bcc6ea16d212a12bca8a63df161c60efde7`.
- `record-identity.env`: exact isolated-run environment,
  SHA256 `8ed16ee8496c2f016337816203bd7156dcf896a883af126eac199b7bb3572851`.
- `xpu-runtime-binaries.sha256`: hashes recorded before the server run.

## Original run directories

`record-run-directories.tar.gz` is a deterministic archive of:

```text
qwen27-fullgraph-transaction-quality-20260711T2050Z/
tp2-fullgraph-transaction-crossover-20260711T2030Z/
```

It includes the isolated server log, smoke/bench/quality stdout, source heads,
Git status, exact working patches, launcher snapshots, model endpoint identity,
all four crossover run directories, and thermal/window marker files. Archive
SHA256:

```text
50ca5f9814adb45002e237a881a6be865434b08d226d85cb9a131cb5f74c58f8
```

Every one of its 130 files is independently listed in
`record-run-directories.SHA256SUMS`; `verify-packet.py` streams the archive and
checks the file set and every digest without extracting into the repository.

The archive was created with sorted names, numeric owner/group zero, and a
fixed UTC mtime. PIDs and original absolute paths are historical metadata, not
inputs to a new run. A token-pattern scan found no Hugging Face, OpenAI, AWS,
LocalMaxxing, or password credential in the tracked packet or archive.
