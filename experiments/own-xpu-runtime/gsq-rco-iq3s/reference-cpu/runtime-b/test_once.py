import importlib.util,pathlib,unittest
P=pathlib.Path(__file__).with_name('once.py');s=importlib.util.spec_from_file_location('cpu_runtime',P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_environment(self):
  e=M.clean_env();self.assertEqual(e['OMP_NUM_THREADS'],'2');self.assertFalse(set(e)&{'LD_PRELOAD','LD_LIBRARY_PATH','GGML_BACKEND_PATH','ONEAPI_DEVICE_SELECTOR','SYCL_DEVICE_FILTER'})
 def test_dtypes(self):
  M.dtype_log('K (bf16): 1, V (bf16): 2\nR (f32): 1, S (f32): 2, P (f32): 3')
  for text in ['K (f16):1 V (bf16):2\nR (f32) S (f32) P (f32)','K (bf16) V (bf16)\nR (f32) S (bf16) P (f32)']:
   with self.assertRaises(RuntimeError):M.dtype_log(text)
 def test_response(self):
  r={'tokens_evaluated':87,'truncated':False,'tokens':[1,2],'stop':True,'stop_type':'eos','generation_settings':{'temperature':-1,'samplers':['temperature'],'n_predict':32,'ignore_eos':False,'n_probs':32,'post_sampling_probs':False},'completion_probabilities':[{}]}
  M.response_check(r);r['generation_settings']['samplers']=['top_k','temperature']
  with self.assertRaises(RuntimeError):M.response_check(r)
 def test_no_retry_code(self):
  text=P.read_text();self.assertEqual(text.count('subprocess.Popen('),1);self.assertEqual(text.count("request_http('POST'"),1);self.assertEqual(text.count('p.send_signal('),1);self.assertNotIn('SIGKILL',text);self.assertIn('explicit admitted plan hash required',text)
class CallbackTests(unittest.TestCase):
 def test_actual_source_level(self):
  source=pathlib.Path('/home/steve/build/flash-next-iq3-baseline-20261010/llama.cpp')
  callback=(source/'common/log.cpp').read_text();common=(source/'common/common.cpp').read_text();args=(source/'common/arg.cpp').read_text()
  self.assertIn('case GGML_LOG_LEVEL_INFO:  return LOG_LEVEL_TRACE;',callback)
  self.assertIn('if (verbosity <= common_log_verbosity_thold)',callback)
  self.assertIn('llama_log_set(common_log_default_callback, NULL)',common)
  self.assertIn('"--log-verbosity"',args)
  self.assertIn("'--log-verbosity','4'",P.read_text())
  # INFO from llama maps to4: threshold3 suppresses,4 includes it.
  self.assertFalse(4<=3);self.assertTrue(4<=4)
if __name__=='__main__':unittest.main()
