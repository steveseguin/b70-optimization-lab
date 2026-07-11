from pathlib import Path

from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, SyclExtension


ROOT = Path(__file__).resolve().parent


setup(
    name="qwen27-fused-postattn-rms-w4a16",
    version="0.0.1",
    ext_modules=[
        SyclExtension(
            name="qwen27_fused_postattn_rms_w4a16_ext",
            sources=[str(ROOT / "csrc" / "fused_postattn_rms_w4a16.sycl")],
            extra_compile_args={
                "cxx": ["-O3", "-std=c++20"],
                "sycl": [
                    "-O3",
                    "-std=c++20",
                    "-ffast-math",
                    "-fsycl-device-code-split=per_kernel",
                ],
            },
            py_limited_api=False,
        )
    ],
    cmdclass={"build_ext": BuildExtension.with_options(use_ninja=True)},
)
