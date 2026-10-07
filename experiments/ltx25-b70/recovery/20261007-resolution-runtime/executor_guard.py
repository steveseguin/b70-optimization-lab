"""One-shot process-local execution guard for the resolution experiment.

No model imports or device operations at import. The launcher provides its sealed
authority and safety adapter. Success is announced only after post-request checks;
refusals become normal failed Comfy history entries, never a worker restart.
"""
import functools
import traceback


def request_name(prompt):
    names = {node['inputs']['run_name'] for node in prompt.values()
             if 'run_name' in node.get('inputs', {})}
    if len(names) != 1:
        raise RuntimeError('Every named node must bind one resolution request')
    return names.pop()


def install(executor_class, authority, before_request, after_request, on_failure=None):
    if getattr(executor_class, '_resolution_guard_installed', False):
        raise RuntimeError('Resolution executor guard cannot be installed twice')
    original = executor_class.execute_async

    @functools.wraps(original)
    async def guarded(self, prompt, prompt_id, extra_data=None, execute_outputs=None):
        extra_data = {} if extra_data is None else extra_data
        execute_outputs = [] if execute_outputs is None else execute_outputs
        # Comfy reads these even after a pre-execution refusal.
        self.success = False
        self.status_messages = []
        self.history_result = {'outputs': {}, 'meta': {}}
        self.server.client_id = extra_data.get('client_id')
        original_message = self.add_message
        prior_instance_message = self.__dict__.get('add_message')
        had_instance_message = 'add_message' in self.__dict__
        deferred_success = []

        def checked_message(event, data, broadcast):
            if event == 'execution_success':
                deferred_success.append((event, dict(data), broadcast))
            else:
                original_message(event, data, broadcast)

        self.add_message = checked_message
        began = False
        try:
            name = request_name(prompt)
            row = authority.begin(name, prompt, prompt_id)
            began = True
            before_request(row, prompt_id)
            await original(self, prompt, prompt_id, extra_data, execute_outputs)
            if len(deferred_success) != 1 or deferred_success[0][1].get('prompt_id') != prompt_id:
                raise RuntimeError('Native executor did not finish exactly one successful request')
            after_request(row, prompt_id)
            # Validate success against genuine executor messages, but do not broadcast
            # it until the authority has durably recorded the request's completion.
            messages = [*self.status_messages,
                        (deferred_success[0][0], deferred_success[0][1])]
            authority.finish(messages)
            self.success = True
            original_message(*deferred_success[0])
        except Exception as error:
            self.success = False
            halt_receipt_error = None
            failure_cleanup_error = None
            if began and on_failure is not None:
                try:
                    # Release a scoped native no-eviction wrapper after a failed
                    # numerical request; its failure latch remains permanent.
                    on_failure(row, prompt_id, error)
                except Exception as cleanup_error:
                    failure_cleanup_error = repr(cleanup_error)
            try:
                # Authority sets its permanent in-memory latch before any write.
                # A full disk must not turn a failed prompt into a dead worker.
                authority.halt(error)
            except Exception as receipt_error:
                halt_receipt_error = repr(receipt_error)
            original_message('execution_error', {
                'prompt_id': prompt_id, 'node_id': 'resolution-authority',
                'node_type': 'ResolutionExperimentGuard', 'executed': [],
                'exception_message': str(error), 'exception_type': type(error).__name__,
                'traceback': traceback.format_exception(type(error), error, error.__traceback__),
                'current_inputs': {}, 'current_outputs': list(self.history_result.get('outputs', {})),
                'resolution_execution_began': began,
                'halt_receipt_error': halt_receipt_error,
                'failure_cleanup_error': failure_cleanup_error,
            }, False)
        finally:
            if had_instance_message:
                self.add_message = prior_instance_message
            else:
                del self.add_message

    executor_class.execute_async = guarded
    executor_class._resolution_guard_installed = True
    return {'installed': True, 'original_module': original.__module__,
            'original_qualname': original.__qualname__,
            'behavior': 'delay success until postchecks; failed requests halt, never retry'}
