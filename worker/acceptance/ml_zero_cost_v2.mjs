// Prospective v2 gate. The original behavioral gate remains unchanged.
// Run from the task workspace; acceptance files live in a separate read-only mount.
import './ml_zero_cost.mjs';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';

execFileSync(process.execPath, ['scripts/stamp-engine.mjs', '--check'], {
  cwd: process.cwd(), stdio: 'pipe', timeout: 30000
});

// The fake DOM used above checks arithmetic, not HTML number-input validity.
// Explicit zero must also be within the actual controls' declared valid range.
const html = fs.readFileSync('index.html', 'utf8');
function attributes(tag) {
  const result = {};
  for (const match of tag.matchAll(/([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
    result[match[1].toLowerCase()] = match[2] ?? match[3] ?? match[4];
  }
  return result;
}
const inputs = [...html.matchAll(/<input\b[^>]*>/gi)].map(match => attributes(match[0]));
for (const id of ['hoursPerDay', 'costPerKwh']) {
  const matches = inputs.filter(input => input.id === id);
  assert.equal(matches.length, 1, `Browser control ${id} must exist exactly once`);
  const control = matches[0];
  assert.equal(control.type, 'number', `Browser control ${id} must remain numeric`);
  for (const [attribute, accepts] of [['min', value => value <= 0], ['max', value => value >= 0]]) {
    if (control[attribute] !== undefined) {
      const value = Number(control[attribute]);
      assert.ok(Number.isFinite(value) && accepts(value), `Browser control ${id} ${attribute} must allow zero`);
    }
  }
  if (control.step !== 'any') {
    const step = control.step === undefined ? 1 : Number(control.step);
    const base = control.min !== undefined ? Number(control.min) : Number(control.value || 0);
    assert.ok(Number.isFinite(step) && step > 0, `Browser control ${id} must have a valid step`);
    const position = -base / step;
    assert.ok(Math.abs(position - Math.round(position)) < 1e-9, `Browser control ${id} step must allow zero`);
  }
}
console.log('PASS: v2 zero-cost behavior, current browser cache stamp, and zero-valid usage controls');
