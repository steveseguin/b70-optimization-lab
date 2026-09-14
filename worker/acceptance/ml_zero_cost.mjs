// Independent acceptance; only Node built-ins and the workspace's own SDK/UI loader.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const root = process.cwd();
execFileSync(process.execPath, ['scripts/build-sdk.mjs'], {cwd: root, stdio: 'pipe', timeout: 30000});
const {createEngine} = await import(pathToFileURL(path.join(root, 'dist/mlbottleneck-engine.mjs')).href);
const engine = createEngine();
const request = {model: 'llama3_8b', hardware: 'RTX 4090', runtime: 'vllm', quantization: 'fp16'};
const normal = engine.predict({...request, usage: {hoursPerDay: 8, costPerKwh: 0.12}});
assert.ok(normal.power.costPerDay > 0, 'Positive-price control must have a positive daily cost');
assert.deepEqual(engine.predict(request).power, normal.power, 'Omitted usage should retain its documented defaults');
for (const [usage, expected] of [
  [{hoursPerDay: 8, costPerKwh: 0}, {costPerDay: 0, costPer1KTokens: 0}],
  [{hoursPerDay: 0, costPerKwh: 0.12}, {costPerDay: 0}],
]) {
  const result = engine.predict({...request, usage});
  for (const [key, value] of Object.entries(expected)) assert.equal(result.power[key], value, `SDK ${key} must honor ${JSON.stringify(usage)}`);
  assert.deepEqual(result.decode, normal.decode, 'Cost inputs must not alter decode predictions');
  assert.deepEqual(result.prefill, normal.prefill, 'Cost inputs must not alter prefill predictions');
}
const {loadApp} = await import(pathToFileURL(path.join(root, 'tests/load-index-app.mjs')).href);
const app = loadApp();
for (const [hours, price] of [[8, 0], [0, 0.12]]) {
  app.setValue('hoursPerDay', hours);
  app.setValue('costPerKwh', price);
  const cost = app.sandbox.calculatePowerAndCost(app.hooks.getDevices(), 100);
  assert.equal(cost.dailyCost, 0, `Browser daily cost must honor ${hours} hours and ${price} price`);
  assert.equal(cost.hoursPerDay, hours);
  assert.equal(cost.costPerKwh, price);
}
console.log('PASS: explicit zero usage/price honored by SDK and browser, positive/default behavior preserved');
