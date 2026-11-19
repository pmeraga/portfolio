import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assessOrder, validateConstraints } from '../src/coverage.js';
const line = (name, tags, quantity = 1, serves = 1) => ({ name, tags, quantity, serves });
const constraints = (groups, headcount = 2) => ({ headcount, groups, budget_per_person: 20, confirmed: true, notes: '' });
test('vegetarian does not satisfy vegan; unknown tags do not satisfy restrictions', () => {
  const a = assessOrder([line('Meal', 'vegetarian', 2)], 20, constraints([{ count: 2, tags: ['vegan'] }]));
  assert.equal(a.groups[0].covered, 0);
  assert.equal(a.status, 'needs-review');
});
test('allocation reroutes portions to avoid double counting and greedy failures', () => {
  const a = assessOrder([line('Both', 'vegan,gluten-free'), line('Vegan', 'vegan')], 30,
    constraints([{ count: 1, tags: ['vegetarian'] }, { count: 1, tags: ['vegan', 'gluten-free'] }]));
  assert.equal(a.status, 'covered');
  assert.equal(a.groups.reduce((s, g) => s + g.covered, 0), 2);
  assert.equal(a.groups[1].items[0].name, 'Both');
});
test('shared platters, small groups, delivery budget and unconfirmed notes', () => {
  const c = constraints([{ count: 2, tags: ['vegan'] }], 3);
  const a = assessOrder([line('Tray', 'vegan', 1, 4)], 65, c);
  assert.equal(a.portions, 4); assert.equal(a.surplus, 1);
  assert.equal(a.status, 'needs-review'); assert.equal(a.budget, 60);
  assert.equal(assessOrder([line('Tray', 'vegan', 1, 4)], 45, { ...c, confirmed: false }).status, 'needs-review');
});
test('reject invalid and overlapping group counts; historical orders remain unknown', () => {
  assert.throws(() => validateConstraints(constraints([{ count: 3, tags: ['vegan'] }]), {}));
  assert.throws(() => validateConstraints({ ...constraints([]), headcount: 0 }, {}));
  assert.equal(assessOrder([], 0, null).status, 'needs-review');
});

test('one affordable vegan platter covers vegan, vegetarian and unrestricted diners', () => {
  const a = assessOrder([line('Shared vegan platter', 'vegan', 1, 6)], 54,
    { ...constraints([{ count: 2, tags: ['vegan'] }, { count: 2, tags: ['vegetarian'] }], 6), budget_per_person: 9 });
  assert.equal(a.status, 'covered');
  assert.equal(a.cost_per_person, 9);
  assert.deepEqual(a.groups.map(g => g.covered), [2, 2, 2]);
  assert.equal(a.groups.flatMap(g => g.items).reduce((s, i) => s + i.portions, 0), 6);
});

const group = (count, ...tags) => ({ count, tags });
test('office example: 6 vegetarian, 2 vegan, 1 gluten-free, 3 no pork', () => {
  const c = constraints([group(6, 'vegetarian'), group(2, 'vegan'), group(1, 'gluten-free'), group(3, "don't eat pork")], 30);
  c.notes = "6 vegetarian, 2 vegan, 1 gluten-free. 3 people don't eat pork.";
  const a = assessOrder([line('Plant meals', 'vegan', 11), line('GF meal', 'gluten-free'), line('Other meals', '', 18)], 500, c);
  assert.equal(a.status, 'covered');
  assert.deepEqual(a.groups.map(g => g.covered), [6, 2, 1, 3, 18]);
});
test('original 120-person customer: 14 restricted diners remain individually accounted for', () => {
  const c = constraints([group(6, 'vegetarian'), group(4, 'vegan'), group(1, 'gluten-free'), group(3, 'pork-free')], 120);
  const a = assessOrder([line('Universal tray', 'vegan,gluten-free', 12, 10)], 1200, c);
  assert.equal(a.status, 'covered');
  assert.deepEqual(a.groups.map(g => g.covered), [6, 4, 1, 3, 106]);
  assert.equal(a.cost_per_person, 10);
});
for (const [restriction, tags, expected] of [
  ['vegan', 'vegetarian', 0], ['vegetarian', 'vegan', 1],
  ['pork-free', 'vegetarian', 1], ['no pork', 'vegan', 1],
  ['pork-free', 'gluten-free', 0], ['gluten-free', 'vegan', 0],
  ['dairy-free', 'vegetarian', 0], ['dairy-free', 'vegan', 1],
  ['halal', 'pork-free', 0], ['kosher', 'vegan', 0],
  ['nut-free', 'vegan', 0], ['sesame-free', 'sesame-free', 1],
  [' GLUTEN FREE ', ' GF ', 1], ['custom-restriction', 'custom-restriction', 1],
  ['constructor', '', 0], ['__proto__', '__proto__', 1],
]) test(`evidence: ${tags || '(unknown)'} → ${restriction}: ${expected}`, () => {
  assert.equal(assessOrder([line('Meal', tags)], 10, constraints([group(1, restriction)], 1)).groups[0].covered, expected);
});
test('combined restrictions cannot be satisfied by two different incompatible dishes', () => {
  const a = assessOrder([line('Vegan', 'vegan'), line('GF', 'gluten-free')], 15, constraints([group(1, 'vegan', 'gluten-free')], 1));
  assert.equal(a.groups[0].covered, 0);
});
test('free-text notes alone never become verified dietary coverage', () => {
  const a = assessOrder([line('Unknown', '', 30)], 300, { ...constraints([], 30), notes: '6 vegetarian, 2 vegan, 1 gluten-free. 3 people do not eat pork.', confirmed: false });
  assert.equal(a.status, 'needs-review');
});
test('a shortage stays visible even when total portions equal headcount', () => {
  const a = assessOrder([line('Vegetarian', 'vegetarian', 10)], 100, constraints([group(2, 'vegan')], 10));
  assert.equal(a.portions, 10); assert.equal(a.groups[0].covered, 0);
  assert.equal(a.status, 'needs-review');
});
test('missing tags remain unknown and single-diner orders work', () => {
  const a = assessOrder([{ name: 'Unknown', quantity: 1, serves: 1 }], 10, constraints([group(1, 'vegan')], 1));
  assert.equal(a.groups[0].covered, 0);
  assert.equal(assessOrder([line('Meal', 'vegan')], 10, constraints([group(1, 'vegan')], 1)).status, 'covered');
});
test('invalid portions fail quickly rather than corrupting allocation', () => {
  for (const n of [0, -1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => assessOrder([line('Meal', 'vegan', n)], 10, constraints([], 1)));
    assert.throws(() => assessOrder([line('Meal', 'vegan', 1, n)], 10, constraints([], 1)));
  }
  assert.throws(() => assessOrder([], NaN, constraints([], 1)));
  assert.throws(() => assessOrder([], 10, constraints([group(2, 'vegan')], 1)));
});
test('allocation agrees with an independent exhaustive matcher across 256 small menus', () => {
  const restrictions = ['a', 'b', 'c', 'd'];
  // Enumerate menus with shortages, shared compatibility, and competing assignments.
  for (let mask = 0; mask < 256; mask++) {
    const support = Array.from({ length: 4 }, (_, i) => [restrictions[(mask >> (2 * i)) & 3], ...(i % 2 ? ['a'] : [])]);
    function best(i, used) {
      if (i === 4) return 0;
      let max = best(i + 1, used);
      for (let j = 0; j < 4; j++) if (!(used & (1 << j)) && support[j].includes(restrictions[i]))
        max = Math.max(max, 1 + best(i + 1, used | (1 << j)));
      return max;
    }
    const lines = support.map((tags, i) => line(`Meal ${i}`, tags.join(',')));
    const c = constraints(restrictions.map(t => group(1, t)), 4);
    const a = assessOrder(lines, 40, c);
    assert.equal(a.groups.reduce((s, g) => s + g.covered, 0), best(0, 0));
    const reversed = assessOrder([...lines].reverse(), 40, { ...c, groups: [...c.groups].reverse() });
    assert.equal(reversed.status, a.status);
    for (const l of lines) assert.ok(a.groups.flatMap(g => g.items).filter(i => i.name === l.name).reduce((s, i) => s + i.portions, 0) <= 1);
  }
});
