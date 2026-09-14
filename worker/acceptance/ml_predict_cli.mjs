// Independent subprocess acceptance for the documented prediction CLI.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';

const run = options => spawnSync(process.execPath,
  ['scripts/predict.mjs', 'llama3_8b', 'RTX 4090', ...options],
  {cwd: process.cwd(), encoding: 'utf8', timeout: 15000, maxBuffer: 1024 * 1024});
const control = run(['--count', '1', '--prompt', '64', '--output', '32', '--batch', '2']);
assert.equal(control.status, 0, 'Documented valid numeric arguments must still succeed: ' + control.stderr);
assert.match(control.stdout, /decode/i);
assert.match(control.stdout, /prefill/i);
assert.doesNotMatch(control.stdout, /NaN|Infinity/);
for (const option of ['count', 'prompt', 'output', 'batch']) {
  for (const values of [['banana'], ['0'], ['-1'], ['1.5'], ['2junk'], []]) {
    const result = run([`--${option}`, ...values]);
    assert.equal(result.error, undefined, `CLI timed out or could not start for --${option} ${values.join(' ')}`);
    assert.notEqual(result.status, 0, `Invalid --${option} ${values.join(' ')} must be rejected`);
    const message = result.stderr + result.stdout;
    assert.match(message, new RegExp(option, 'i'), `Error must identify --${option}: ${message}`);
    assert.doesNotMatch(message, /TypeError:|ReferenceError:|\n\s+at (?:file:|\w)/, `Invalid argument must not expose an internal stack trace: ${message}`);
  }
}
console.log('PASS: numeric CLI errors are actionable; valid documented options still work');
