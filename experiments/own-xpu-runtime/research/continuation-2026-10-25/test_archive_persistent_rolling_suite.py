"""Full-suite preservation must retain its narrower final-state qualification."""
import json
from pathlib import Path
import tempfile
import unittest
import archive_persistent_rolling_suite as archive

class SuiteArchiveAdmissionTests(unittest.TestCase):
    def valid(self,run):
        d=dict(schema='ownrt.persistent-rolling-suite-proof.v1',passed=True,source_run=str(run),
               requests=12,output_tokens=5965,check_policy='measured',provider_survival_evidence='not-collected')
        for k in ('output_tokens_exact','provenance_passed','all_cold_resets_checked','mandatory_restore_checks_passed',
                  'actual_provider','actual_proposals_consumed','final_target_state_exact','final_draft_authenticated'):d[k]=True
        for k in ('byte_verification_enabled','provider_survival_checks_enabled','all_requests_full_state_parity',
                  'final_draft_state_parity','scripted_oracle_assisted','speed_claim','certified'):d[k]=False
        return d

    def test_incomplete_or_overclaimed_summary_refused_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';proof=Path(tmp)/'proof';run.mkdir();proof.mkdir()
            (run/'persistent-rolling-result.json').write_text('{}');valid=self.valid(run)
            for key in valid:
                for missing in (False,True):
                    d=dict(valid)
                    if missing:d.pop(key)
                    elif type(d[key])is bool:d[key]=not d[key]
                    elif type(d[key])is int:d[key]+=1
                    else:d[key]='wrong'
                    (proof/'summary.json').write_text(json.dumps(d))
                    with self.subTest(key=key,missing=missing),self.assertRaisesRegex(ValueError,'PASSED explicit twelve-request'):
                        archive.full(run,proof,Path(tmp)/'out.tgz',Path(tmp)/'receipt.json')
                    self.assertFalse((Path(tmp)/'out.tgz').exists())
            (proof/'summary.json').write_text(json.dumps(valid))
            with self.assertRaises(FileNotFoundError):archive.full(run,proof,Path(tmp)/'out.tgz',Path(tmp)/'receipt.json')

    def test_planner_bridge_preserved_and_mutation_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def source(name,raw=b'{}'):
                p=root/name;p.write_bytes(raw);return archive.identity(p)
            summary=source('summary');plan=source('plan')
            transition={k:source(k) for k in ('before_source','after_source','patch','cpu_review','independent_review')}
            receipt=source('transition',json.dumps(transition).encode())
            items=[dict(summary=summary,plan=plan,execution_closure=dict(planner_transition=receipt)) for _ in range(2)]
            sources=archive.prerequisite_sources(dict(prerequisites=items))
            self.assertEqual(len(sources),10)
            self.assertEqual(len({name for _,name in sources}),10)
            (root/'patch').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'evidence changed'):
                archive.prerequisite_sources(dict(prerequisites=items))

if __name__=='__main__':unittest.main()
