# Native-MTP/V1 control. CPU-only build; no GPU or model access.
FROM vllm/vllm-openai-xpu@sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41
COPY upstream-python.sha256 candidate-python.sha256 accepted-overlay.patch /opt/amd-transfer/
RUN cd /opt/venv/lib/python3.12/site-packages && sha256sum -c /opt/amd-transfer/upstream-python.sha256 \
    && patch --batch --fuzz=0 -p1 < /opt/amd-transfer/accepted-overlay.patch \
    && sha256sum -c /opt/amd-transfer/candidate-python.sha256 \
    && python -c "import pathlib, ast; [ast.parse(pathlib.Path(line.split()[1]).read_text()) for line in pathlib.Path('/opt/amd-transfer/candidate-python.sha256').read_text().splitlines()]"
ENV VLLM_USE_V2_MODEL_RUNNER=0
COPY draft-shortlists/ /opt/draft-shortlists/
COPY kernel-artifacts/ /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/
WORKDIR /
RUN python -c "import torch, vllm, importlib.metadata as m; import vllm_xpu_kernels._xpu_C; assert vllm.__file__.startswith('/opt/venv/'),vllm.__file__; assert not torch.xpu.is_initialized(); assert not torch.cuda.is_initialized(); print('CPU import check',vllm.__file__,torch.__version__,vllm.__version__,m.version('vllm_xpu_kernels'))"
LABEL neural.download.build.lane="qwen38-fp8-mtp-lossless-transfer-20260914-control" \
      neural.download.kernel.head="6d92b1bfbf32767ecda8e819613eb151e70030ad" \
      neural.download.kernel.patch="onednn 0e2a5bfe r137a+r137b+r221" \
      neural.download.upstream.commit="dc36fcce902a63eab06c1b93a5c4a5ee178a0c56" \
      neural.download.runner="V1-native-MTP-only" \
      neural.download.status="unqualified-control-rebase"
