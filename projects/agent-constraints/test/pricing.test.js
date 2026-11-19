import { test } from 'node:test';
import assert from 'node:assert/strict';
import { calculateCharges, pricingPolicy } from '../src/pricing.js';
import { enforceBudget, validateConstraints } from '../src/coverage.js';
const policy = pricingPolicy({});
test('all charges are itemized and included in total', () => {
  const p = calculateCharges(10000, 2, 15, policy);
  assert.equal(p.subtotal, 100);
  assert.equal(p.delivery_fee, 15);
  assert.equal(p.distance_fee, 0);
  assert.equal(p.vendor_fee, 3);
  assert.equal(p.tax, 9.27);
  assert.equal(p.tip, 15);
  assert.equal(p.total, 142.27);
  assert.throws(() => enforceBudget(p.total, { headcount: 7, budget_per_person: 20 }), /exceeds/);
});
test('distance threshold and surcharge are independent of search radius', () => {
  assert.equal(calculateCharges(10000, 2, 10, policy).distance_fee, 0);
  assert.equal(calculateCharges(10000, 2.01, 10, policy).distance_fee, 0.75);
  assert.equal(calculateCharges(10000, 3, 10, policy).distance_fee, 0.75);
  assert.equal(calculateCharges(10000, 3.01, 10, policy).distance_fee, 1.5);
});
test('preset and custom tips are calculated on food only', () => {
  for (const tip of [0, 10, 15, 20, 25, 17.5, 100])
    assert.equal(calculateCharges(10000, 2, tip, policy).tip, tip);
  for (const tip of [-1, NaN, Infinity, 101])
    assert.throws(() => calculateCharges(10000, 2, tip, policy), /Tip/);
});
test('settings validate and policy is controlled by server rather than client', () => {
  assert.throws(() => pricingPolicy({ ORDER_TAX_PERCENT: '-1' }), /Invalid/);
  const c = validateConstraints({ tip_percent: 17.5, pricing_policy: { tax_percent: 0 } }, { headcount: 2, budget_per_person: 20 });
  assert.equal(c.tip_percent, 17.5);
  assert.notDeepEqual(c.pricing_policy, { tax_percent: 0 });
  assert.throws(() => validateConstraints({ tip_percent: -1 }, { headcount: 2, budget_per_person: 20 }), /Tip/);
  const custom = pricingPolicy({ ORDER_TAX_PERCENT: '0', ORDER_VENDOR_FEE_PERCENT: '0', ORDER_VENDOR_FEE_FIXED: '2' });
  assert.equal(calculateCharges(10000, 2, 10, custom).total, 127);
});
