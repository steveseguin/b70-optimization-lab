import os

os.environ.setdefault("CC", "icx")
os.environ.setdefault("CXX", "icpx")

from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, SyclExtension


sycl_targets = os.environ.get("QWEN27_ESIMD_AR_SYCL_TARGETS", "spir64")
sycl_flags = ["-fsycl", f"-fsycl-targets={sycl_targets}"]
if sycl_device := os.environ.get("QWEN27_ESIMD_AR_SYCL_DEVICE"):
    sycl_flags.extend(["-Xs", f"-device {sycl_device}"])

setup(
    name="qwen27_esimd_allreduce",
    version="0.0.1",
    ext_modules=[
        SyclExtension(
            name="qwen27_esimd_allreduce",
            sources=["qwen27_esimd_allreduce.cpp"],
            extra_compile_args={
                "cxx": [
                    "-O3",
                    "-std=c++20",
                    "-fPIC",
                    *sycl_flags,
                ],
            },
            extra_link_args=[*sycl_flags, "-lze_loader"],
        )
    ],
    cmdclass={"build_ext": BuildExtension},
)
