import assert from 'node:assert/strict';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const {parseLlamaBenchDecodeContext:parse}=await import(pathToFileURL(path.join(process.cwd(),'scripts/llama-bench-context.mjs')));
for(const [command,expected] of [
  ['llama-bench -p 4096 -n 512',0],
  ['llama-bench -d 0',0],
  ['llama-bench -d 512',512],
  ['llama-bench --n-depth=1024',1024],
  ['"/opt/test tools/llama-bench" --n-depth "2048" -p 512',2048],
])assert.deepEqual(parse(command),{decodeDepthTokens:expected,decodeMeasurementIssue:null},`Valid control must be preserved: ${command}`);
assert.deepEqual(parse('llama-server -d 512'),{decodeDepthTokens:null,decodeMeasurementIssue:null},'Unrelated executable must remain unknown');
const malformed=[
  'llama-bench -d 512 --n-depth',
  'llama-bench --n-depth=512 -d',
  'llama-bench -d 512 --n-depth=',
  'llama-bench --n-depth 0 -d=',
  'llama-bench -d "512" --n-depth   ',
  'llama-bench -d 0,4096',
  'llama-bench -d 512 -d 1024',
  'llama-bench --n-depth',
  'llama-bench -d nope',
  'llama-bench -d 512 -pg 256,128',
];
const failures=[];
for(const command of malformed){
  const parsed=parse(command);console.log(JSON.stringify({command,parsed}));
  if(parsed.decodeDepthTokens!==null||typeof parsed.decodeMeasurementIssue!=='string'||!parsed.decodeMeasurementIssue.trim())failures.push({command,parsed});
}
assert.equal(failures.length,0,`An incomplete depth flag must not become a precise decode-depth measurement: ${JSON.stringify(failures)}`);
console.log('PASS: malformed duplicate depth flags, existing ambiguity checks, zero/positive depths, quoted values, and unrelated-command control');
