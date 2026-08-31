# Qwen3.8 active packaged GDN exception capture D38s preregistration

Date: 2026-08-31

Status: **preregistered before D38s model requests**

D38/D38r both returned an empty response; neither preserved the server
exception because two sequential runner fail paths lacked log capture. D38s
uses the unchanged D38 stage hook and packaged image after wrapping the
benchmark-client invocation itself. The immediate and only required outcome is
either a valid process-1 trace or a preserved traceback explaining the hook
failure. Do not interpret this as a four-process model result.
