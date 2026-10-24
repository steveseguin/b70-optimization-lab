# Corrected CPU-only build configuration

The original configure attempt failed at ggml/src/CMakeLists.txt370 because
GGML_BACKEND_DIR requires dynamic backends. It remains preserved with its source,
log and failed receipt. This additive recipe removes only that directory flag,
keeps GGML_BACKEND_DL OFF and every accelerator OFF, and uses a fresh USB root.
The reviewed bounded root driver is reused unchanged. Runtime still requires
clean isolated executable/CWD search paths and offline ELF checks; no model or
reference execution is implied by building.
