"""CPU-only integration/admission regression receipt."""
import io,json,unittest
from pathlib import Path
from storage import digest
P=Path(__file__).resolve().parent
def main():
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromNames(['test_p49_integration','test_queue_runner','test_p49_dispatch'])
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    names=('test_p49_integration.py','test_queue_runner.py','test_p49_dispatch.py','p49_dispatch.py','window.py','queue_runner.py','storage.py','memory_gate.py','p49_python_gate.py')
    row=dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),log=stream.getvalue(),
        sources_sha256={name:digest(P/name) for name in names})
    (P/'p49-python-gates.json').write_text(json.dumps(row,indent=2)+'\n')
    print(stream.getvalue());assert row['passed']
if __name__=='__main__':main()
