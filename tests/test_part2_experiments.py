import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch, Mock

from minicode.selector_training import sha256_file

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('part2_runner', ROOT/'scripts/run_part2_experiments.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ExperimentTests(unittest.TestCase):
    def export(self, path):
        path.mkdir()
        (path/'adapter').mkdir()
        (path/'adapter/adapter_model.safetensors').write_bytes(b'fixture-not-real-weights')
        artifacts = {}
        for name in ('base_test','lora_test','lora_no_context_test'):
            for suffix in ('_predictions.jsonl','_report.json'):
                filename=name+suffix
                (path/filename).write_text('{}\n')
                artifacts[filename]=sha256_file(path/filename)
        manifest = {'status':'local_evaluation_complete','protocol':runner.PROTOCOL_VERSION,
            'code_sha256':{name:sha256_file(ROOT/name) for name in
                ('src/minicode/selector_protocol.py','src/minicode/selector_training.py')},
            'dataset_sha256':sha256_file(ROOT/'data/tool_selection/examples.jsonl'),
            'adapter_files':{'adapter_model.safetensors':sha256_file(path/'adapter/adapter_model.safetensors')},
            'artifact_sha256':artifacts,'config':{'model':'fixture'},'model_revision':'fixture-revision'}
        (path/'run_manifest.json').write_text(json.dumps(manifest))

    def test_all_conditions_use_same_budgets_and_record_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.export(root/'training')
            fake=Mock(metadata={'fixture':True})
            with patch.object(runner,'LocalSelectorClient',return_value=fake), \
                 patch.object(runner,'QwenClient',return_value=Mock(model='qwen-fixture')), \
                 patch.object(runner.subprocess,'run',return_value=Mock(stdout='sha256:fixture')), \
                 patch.object(runner,'evaluate',return_value={'complete':True,'metrics':{'TaskSuccessRate':0.0}}) as evaluation:
                runner.main(['--run-dir',str(root/'training'),'--output',str(root/'result')])
            calls=evaluation.call_args_list
            self.assertEqual(len(calls),3)
            self.assertIsNone(calls[0].kwargs['tool_selector_factory'])
            self.assertTrue(calls[1].kwargs['tool_selector_factory']().include_context)
            self.assertFalse(calls[2].kwargs['tool_selector_factory']().include_context)
            for call in calls:
                self.assertEqual(call.kwargs['max_llm_calls'],80)
                self.assertEqual(call.kwargs['mode'],'docker')
                self.assertEqual(call.kwargs['image'],'sha256:fixture')
            manifest=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual(manifest['status'],'complete')

    def test_changed_adapter_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'training'
            self.export(path)
            (path/'adapter/adapter_model.safetensors').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Adapter'):
                runner.validate_export(path)

    def test_summary_recomputes_predictions_and_detects_changed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            dataset=ROOT/'data/tool_selection/examples.jsonl'
            (path/'dataset.jsonl').write_bytes(dataset.read_bytes())
            rows=[json.loads(line) for line in dataset.read_text().splitlines()]
            predictions=''.join(json.dumps({'id':r['id'],'tool':r['label']})+'\n'
                                for r in rows if r['split']=='test')
            artifacts={}
            for name in ('base_test','lora_test','lora_no_context_test'):
                filename=name+'_predictions.jsonl'
                (path/filename).write_text(predictions)
                artifacts[filename]=sha256_file(path/filename)
            (path/'run_manifest.json').write_text(json.dumps({'status':'local_evaluation_complete',
                'dataset_sha256':sha256_file(dataset),'artifact_sha256':artifacts}))
            command=[sys.executable,str(ROOT/'scripts/summarize_part2_results.py'),
                '--run-dir',str(path),'--output',str(path/'summary.md')]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('16/16', (path/'summary.md').read_text())
            self.assertIn('PENDENTE', (path/'summary.md').read_text())
            (path/'lora_test_predictions.jsonl').write_text('alterado')
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Predições diferem',result.stderr)
