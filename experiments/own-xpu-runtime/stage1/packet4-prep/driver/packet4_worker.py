"""vLLM-supported worker_cls injection. Imported only by an admitted window.

CPU tests supply a mock vllm.v1.worker.xpu_worker; no real vLLM import is used
by tests. Forward computation always belongs to the unchanged parent worker.
"""
from contextlib import ExitStack
import os
from pathlib import Path

from vllm.v1.worker.xpu_worker import XPUWorker

from window_driver import (PREREG, ORACLE, PROMPT_ID, read, write, require,
                           oracle_assert, sha)


def live_execution(config):
    execution = {'enforce_eager': config.model_config.enforce_eager,
                 'compile_mode': config.compilation_config.mode.name,
                 'graph_mode': config.compilation_config.cudagraph_mode.name,
                 'prefix_caching': config.cache_config.enable_prefix_caching}
    require(execution == read(PREREG)['execution'], 'live engine is not eager/cache-free')
    require(config.parallel_config.tensor_parallel_size == 4
            and config.parallel_config.pipeline_parallel_size == 1
            and config.parallel_config.enable_expert_parallel, 'TP4/EP4 required')
    require(config.scheduler_config.async_scheduling is False, 'async scheduling forbidden')
    require(config.model_config.dtype.__str__() == 'torch.bfloat16', 'BF16 activation required')
    require(config.cache_config.cache_dtype == 'auto', 'original full precision KV required')
    require(config.speculative_config.num_speculative_tokens == 1, 'original MTP1 required')
    return execution


class ExtractionWorker(XPUWorker):
    def load_model(self, *args, **kwargs):
        require(not getattr(self, '_packet4_registered', False), 'second hook registration refused')
        self._packet4_registered = True
        self._packet4_in_target = False
        self._packet4_closed = False
        self._packet4_stack = ExitStack()
        self._packet4_root = Path(os.environ['PACKET4_WINDOW'])
        self._packet4_dir = self._packet4_root / f'rank-{self.rank}'
        try:
            self._packet4_install()
            return super().load_model(*args, **kwargs)
        except BaseException as exc:
            write(self._packet4_root / f'worker-error-{self.rank}.json', {'rank': self.rank, 'error': repr(exc)})
            write(self._packet4_root / 'STOP.json', {'reason': 'worker load/hook failure'})
            # Keep the eager guard installed until cooperative shutdown.
            raise

    def _packet4_install(self):
        import torch
        from vllm.compilation.cuda_graph import CUDAGraphWrapper
        from vllm.models.qwen4_exp.amd.model import Qwen4ExpDecoderLayer
        from adapters.vllm_xpu_certified import eager_guard, install
        from extract_fixtures import Recorder

        p = read(PREREG)
        config = live_execution(self.vllm_config)
        self._packet4_stack.enter_context(eager_guard(config, torch, CUDAGraphWrapper))
        self._packet4_recorder = Recorder(self._packet4_dir, 'flash-next',
             read(self._packet4_root / 'identity.json'), config, read(ORACLE), PROMPT_ID,
             max_bytes=p['rank_bytes'], chunk_bytes=1048576)
        key = 'vllm.models.qwen4_exp.amd.model.Qwen4ExpDecoderLayer'
        self._packet4_stack.enter_context(install(self._packet4_recorder,
            source_id='a367', roots={'a367': os.environ['PACKET4_SOURCE']},
            owners={key: Qwen4ExpDecoderLayer}, metadata=self._packet4_metadata,
            symbol_ids=p['selection']['symbol_ids']))
        write(self._packet4_dir / 'registered.json', {'rank': self.rank, 'pid': os.getpid(),
             'registration_count': 1, 'before_model_construction': True,
             'worker_cls': 'packet4_worker.ExtractionWorker', 'execution': config,
             'selection': p['selection'], 'preregistration_sha256': sha(PREREG)})

    def _packet4_metadata(self, row, bound):
        # No device scalar reads. target-only scope excludes warmup/draft calls.
        if not self._packet4_in_target or bound['self'].layer_idx != 0:
            return None
        hidden = bound['hidden_states']
        m = hidden.shape[0]
        if m not in (1, 2, 6):
            return None
        runner = self.model_runner
        require(runner.input_batch.num_reqs == 1, 'unexpected request count')
        require(self._packet4_scheduled == m, 'padded/changed target row count')
        # Exact same CPU expression as pinned _prepare_inputs for one request.
        positions = (runner.input_batch.num_computed_tokens_cpu[0] + runner.query_pos.np[:m]).tolist()
        require(bound['positions'].numel() == m, 'position count differs')
        return {'M': m, 'N': hidden.shape[-1], 'K': hidden.shape[-1],
                'layer': 0, 'rank': self.rank, 'positions': positions, 'valid_rows': [True] * m}

    def execute_model(self, scheduler_output, *args, **kwargs):
        self._packet4_in_target = True
        self._packet4_scheduled = scheduler_output.total_num_scheduled_tokens
        try:
            return super().execute_model(scheduler_output, *args, **kwargs)
        except BaseException as exc:
            write(self._packet4_root / 'STOP.json', {'reason': 'worker execution/hook failure', 'error': repr(exc)})
            raise
        finally:
            self._packet4_in_target = False

    def shutdown(self):
        if getattr(self, '_packet4_closed', False):
            return
        self._packet4_closed = True
        failure = None
        parent_returned = False
        try:
            recorder = getattr(self, '_packet4_recorder', None)
            if recorder is not None:
                verdict = read(self._packet4_root / 'oracle-verdict.json')
                oracle_assert(verdict['token_ids'], verdict['cached_tokens'],
                              verdict['finish_reason'], self._packet4_dir)
                require(not recorder._pending and recorder.files, 'empty/incomplete rank fixtures')
                write(self._packet4_dir / 'window-extraction.json', {
                    'status': 'PREFIX64-EXACT-UNQUALIFIED', 'rank': self.rank,
                    'fixtures': recorder.files, 'fixture_bytes': recorder.used,
                    'missing_shapes': sorted({1, 2, 6} - {key[2] for key in recorder.seen}),
                    'full_oracle_equal': False, 'full_census_qualified': False,
                    'scope': 'layer0 raw outer boundary; N/K are feature width, not a GEMM census'})
        except BaseException as exc:
            failure = repr(exc)
            if getattr(self, '_packet4_dir', None) and self._packet4_dir.is_dir():
                write(self._packet4_dir / 'VOID.json', {'status': 'VOID', 'reason': failure})
        finally:
            # Original XPU shutdown synchronizes and releases runner/allocator.
            # WorkerProc then destroys distributed environments and exits itself.
            try:
                super().shutdown()
                parent_returned = True
            except BaseException as exc:
                failure = failure or repr(exc)
                raise
            finally:
                if getattr(self, '_packet4_stack', None):
                    self._packet4_stack.close()
                if getattr(self, '_packet4_dir', None) and self._packet4_dir.is_dir():
                    write(self._packet4_dir / 'teardown.json', {
                        'passed': failure is None, 'rank': self.rank, 'pid': os.getpid(),
                        'error': failure, 'parent_shutdown_returned': parent_returned,
                        'distributed_cleanup': 'WorkerProc owns the remaining cleanup; supervisor requires process exit'})
