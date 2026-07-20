"""Fixed-address lifecycle wrapper around the native PyTorch XPU command graph."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

import torch


class GraphState(Enum):
    COLD = auto()
    WARMED = auto()
    BUILT = auto()
    PARITY_QUALIFIED = auto()
    RETIRED = auto()


@dataclass(frozen=True)
class TensorAddress:
    name: str
    data_ptr: int
    shape: tuple[int, ...]
    stride: tuple[int, ...]
    storage_offset: int
    storage_data_ptr: int
    storage_nbytes: int
    dtype: str
    device: str

    @classmethod
    def capture(cls, name: str, tensor: torch.Tensor) -> "TensorAddress":
        return cls(
            name=name,
            data_ptr=tensor.data_ptr(),
            shape=tuple(tensor.shape),
            stride=tuple(tensor.stride()),
            storage_offset=tensor.storage_offset(),
            storage_data_ptr=tensor.untyped_storage().data_ptr(),
            storage_nbytes=tensor.untyped_storage().nbytes(),
            dtype=str(tensor.dtype),
            device=str(tensor.device),
        )


class FixedAddressCommandGraph:
    """Capture and replay a warmed callable on the current PyTorch XPU queue.

    The callable must launch only pre-warmed kernels and return a mapping of
    named output tensors. Inputs and persistent outputs supplied in `bindings`
    are checked before every replay. Capture deliberately calls the low-level
    `XPUGraph.capture_begin` on the current stream instead of the convenience
    context manager, whose default is a side stream.
    """

    def __init__(
        self,
        launch: Callable[[], Mapping[str, torch.Tensor]],
        bindings: Mapping[str, torch.Tensor],
        native_replay: Callable[[int], None] | None = None,
    ) -> None:
        self._launch = launch
        self._native_replay = native_replay
        self._tensors = dict(bindings)
        self._addresses: dict[str, TensorAddress] = {}
        self._outputs: dict[str, torch.Tensor] = {}
        self._graph: torch.xpu.XPUGraph | None = None
        self._queue_identity: int | None = None
        self.state = GraphState.COLD

    @property
    def outputs(self) -> Mapping[str, torch.Tensor]:
        return self._outputs

    @property
    def queue_identity(self) -> int:
        if self._queue_identity is None:
            raise RuntimeError("queue identity is unavailable before warmup")
        return self._queue_identity

    @property
    def graph_exec(self) -> int:
        if self._graph is None or self.state not in {
            GraphState.BUILT,
            GraphState.PARITY_QUALIFIED,
        }:
            raise RuntimeError("graph executable is unavailable")
        return int(self._graph.raw_xpu_graph_exec())

    @property
    def address_manifest(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "data_ptr": address.data_ptr,
                "shape": list(address.shape),
                "stride": list(address.stride),
                "storage_offset": address.storage_offset,
                "storage_data_ptr": address.storage_data_ptr,
                "storage_nbytes": address.storage_nbytes,
                "dtype": address.dtype,
                "device": address.device,
            }
            for name, address in sorted(self._addresses.items())
        }

    def warm(self, repeats: int = 3) -> None:
        if self.state is not GraphState.COLD:
            raise RuntimeError(f"warm requires COLD state, got {self.state.name}")
        if repeats < 1:
            raise ValueError("warmup repeats must be positive")
        stream = torch.xpu.current_stream()
        self._queue_identity = int(stream.sycl_queue)
        for _ in range(repeats):
            self._launch()
        torch.xpu.synchronize()
        if int(torch.xpu.current_stream().sycl_queue) != self._queue_identity:
            raise RuntimeError("current XPU queue changed during warmup")
        self.state = GraphState.WARMED

    def build(self) -> Mapping[str, torch.Tensor]:
        if self.state is not GraphState.WARMED:
            raise RuntimeError(f"build requires WARMED state, got {self.state.name}")
        self._assert_queue()
        graph = torch.xpu.XPUGraph(keep_graph=False)
        graph.capture_begin()
        try:
            outputs = dict(self._launch())
        except BaseException:
            graph.capture_end()
            raise
        graph.capture_end()
        torch.xpu.synchronize()
        self._outputs = outputs
        self._tensors.update(outputs)
        self._addresses = {
            name: TensorAddress.capture(name, tensor)
            for name, tensor in self._tensors.items()
        }
        self._graph = graph
        self.state = GraphState.BUILT
        return self._outputs

    def replay(self) -> Mapping[str, torch.Tensor]:
        if self.state not in {GraphState.BUILT, GraphState.PARITY_QUALIFIED}:
            raise RuntimeError(f"replay requires BUILT state, got {self.state.name}")
        self._assert_queue()
        self._assert_addresses()
        if self._graph is None:
            raise AssertionError("BUILT graph has no native graph object")
        if self._native_replay is None:
            self._graph.replay()
        else:
            self._native_replay(self.graph_exec)
        return self._outputs

    def mark_parity_qualified(self, *, exact: bool) -> None:
        if self.state is not GraphState.BUILT:
            raise RuntimeError("parity qualification requires BUILT state")
        if not exact:
            raise RuntimeError("cannot qualify a graph without exact parity evidence")
        self._assert_addresses()
        self.state = GraphState.PARITY_QUALIFIED

    def retire(self) -> None:
        if self._graph is not None:
            torch.xpu.synchronize()
            self._graph.reset()
        self._graph = None
        self.state = GraphState.RETIRED

    def _assert_queue(self) -> None:
        current = int(torch.xpu.current_stream().sycl_queue)
        if self._queue_identity != current:
            raise RuntimeError(
                "current XPU queue identity drifted: "
                f"expected 0x{self.queue_identity:x}, got 0x{current:x}"
            )

    def _assert_addresses(self) -> None:
        for name, expected in self._addresses.items():
            actual = TensorAddress.capture(name, self._tensors[name])
            if actual != expected:
                raise RuntimeError(
                    f"fixed binding {name!r} drifted: expected {expected}, got {actual}"
                )
