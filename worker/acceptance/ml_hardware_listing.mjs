// Independent acceptance for the public listing API's isolation from engine state.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const root = process.cwd();
execFileSync(process.execPath, ['scripts/build-sdk.mjs'], {cwd: root, stdio: 'pipe', timeout: 30000});
const {createEngine} = await import(pathToFileURL(path.join(root, 'dist/mlbottleneck-engine.mjs')).href);
const engine = createEngine();
const request = {model: 'llama3_8b', hardware: 'RTX 4090', runtime: 'vllm', quantization: 'fp16'};
const baseline = engine.predict(request);
const before = JSON.parse(JSON.stringify(engine.listHardware()));
const listing = engine.listHardware();
const item = listing.find(row => row.key === 'RTX 4090');
assert.ok(item?.computeTFlops, 'Control hardware listing must include its compute specification');
// Immutable listings are acceptable too; attempted edits must never corrupt the engine.
for (const edit of [() => {item.computeTFlops.float16 = 1;},
                    () => {item.computeTFlops.extraAcceptanceField = 7;},
                    () => {item.memoryGB = 1;},
                    () => {listing.pop();}]) {
  try { edit(); } catch (error) { assert.ok(error instanceof TypeError); }
}
assert.deepEqual(engine.listHardware(), before, 'Mutating a returned listing must not change later listings');
assert.deepEqual(engine.predict(request), baseline, 'Mutating a returned listing must not change future predictions');
assert.deepEqual(createEngine().predict(request), baseline, 'A separate engine must remain unaffected');
console.log('PASS: hardware listing edits cannot mutate engine catalogs or predictions');
