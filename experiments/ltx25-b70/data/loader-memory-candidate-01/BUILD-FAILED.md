Incomplete source-only preparation, superseded by `../loader-memory-candidate-02`.
The builder rejected `_encoder_variant = None` because it matched two locations.
Only the candidate diffusion source and its patch were emitted. No Torch import,
checkpoint load, GPU job or prepared/live runtime modification occurred.
The corrected builder anchors the unindented module variable explicitly.
