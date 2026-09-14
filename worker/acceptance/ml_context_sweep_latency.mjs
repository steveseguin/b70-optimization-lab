import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const root=process.cwd();
const build=spawnSync(process.execPath,['scripts/build-sdk.mjs'],{cwd:root,encoding:'utf8',timeout:30000});
assert.equal(build.status,0,`SDK build failed: ${build.stdout}\n${build.stderr}`);
const {createEngine}=await import(pathToFileURL(path.join(root,'dist/mlbottleneck-engine.mjs')));
const engine=createEngine();
const controls={1:{prefill:1442.8,ttft:1.419,decode:42.7},2:{prefill:1627.4,ttft:2.517,decode:84.82},4:{prefill:1763.4,ttft:4.646,decode:167.37}};
const failures=[];
for(const batchSize of [1,2,4]) {
  const request={model:'qwen3.8_27b',hardware:'RTX 4090',quantization:'q4',runtime:'llama_cpp',strategy:'pipeline',promptTokens:2048,outputTokens:128,batchSize};
  const prediction=engine.predict(request);
  const before=JSON.stringify(request);
  const context=engine.sweep(request,{levels:[batchSize],maxContext:4096}).context;
  assert.equal(JSON.stringify(request),before,'Sweep must preserve caller input');
  const point=context.points.find(point=>point.promptTokens===request.promptTokens);
  assert.ok(point,'Sweep must retain the 2048-token comparison point');
  assert.equal(prediction.prefill.tokensPerSecond,controls[batchSize].prefill,'Fix must preserve the existing prefill prediction');
  assert.equal(prediction.prefill.timeToFirstTokenSeconds,controls[batchSize].ttft,'Fix must preserve predict() first-token latency');
  assert.equal(prediction.decode.tokensPerSecond,controls[batchSize].decode,'Fix must preserve decode predictions');
  assert.equal(Math.round(point.prefillTokS*10)/10,prediction.prefill.tokensPerSecond,'Both APIs must describe the same prefill throughput');
  console.log(JSON.stringify({batchSize,predictTTFT:prediction.prefill.timeToFirstTokenSeconds,sweepTTFT:point.ttftSeconds,prefill:point.prefillTokS}));
  for(const sample of context.points) {
    const expected=sample.promptTokens*batchSize/sample.prefillTokS;
    if(Math.abs(sample.ttftSeconds-expected)>Math.max(1e-9,expected*1e-10))failures.push({batchSize,promptTokens:sample.promptTokens,actual:sample.ttftSeconds,expected});
  }
  if(Math.abs(point.ttftSeconds-prediction.prefill.timeToFirstTokenSeconds)>0.00051)failures.push({batchSize,comparison:'predict() disagreement'});
}
assert.equal(failures.length,0,`Context-sweep TTFT must represent the complete batch and agree with predict(): ${JSON.stringify(failures.slice(0,4))}`);
console.log('PASS: batch-1 control, batch-2/batch-4 latency, unchanged decode/prefill predictions, and caller-input preservation');
