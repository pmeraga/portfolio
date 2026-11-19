// Estimates for the demo provider; configure these to match vendor quotes.
export function pricingPolicy(env = process.env) {
  const read = (key, fallback) => {
    const value = env[key] == null || env[key] === '' ? fallback : Number(env[key]);
    if (!Number.isFinite(value) || value < 0) throw new Error(`Invalid pricing setting: ${key}`);
    return value;
  };
  return {
    tax_percent: read('ORDER_TAX_PERCENT', 9),
    vendor_fee_percent: read('ORDER_VENDOR_FEE_PERCENT', 3),
    vendor_fee_fixed: read('ORDER_VENDOR_FEE_FIXED', 0),
    delivery_fee: read('ORDER_DELIVERY_FEE', 15),
    nearby_miles: read('ORDER_NEARBY_MILES', 2),
    distance_fee_percent_per_mile: read('ORDER_DISTANCE_FEE_PERCENT_PER_MILE', 5),
  };
}

export function calculateCharges(subtotalCents, distanceMiles, tipPercent, policy) {
  if (!Number.isSafeInteger(subtotalCents) || subtotalCents < 0 || !Number.isFinite(distanceMiles) || distanceMiles < 0)
    throw new Error('Invalid subtotal or restaurant distance');
  if (!Number.isFinite(tipPercent) || tipPercent < 0 || tipPercent > 100)
    throw new Error('Tip must be between 0% and 100%');
  const baseDelivery = Math.round(policy.delivery_fee * 100);
  const extraMiles = Math.ceil(Math.max(0, distanceMiles - policy.nearby_miles));
  const distanceFee = Math.round(baseDelivery * policy.distance_fee_percent_per_mile / 100 * extraMiles);
  const vendorFee = Math.round(subtotalCents * policy.vendor_fee_percent / 100) + Math.round(policy.vendor_fee_fixed * 100);
  // Tax is modeled on food and vendor fees; voluntary tip and delivery are excluded.
  const tax = Math.round((subtotalCents + vendorFee) * policy.tax_percent / 100);
  const tip = Math.round(subtotalCents * tipPercent / 100);
  const total = subtotalCents + baseDelivery + distanceFee + vendorFee + tax + tip;
  if (![baseDelivery, distanceFee, vendorFee, tax, tip, total].every(n => Number.isSafeInteger(n) && n >= 0))
    throw new Error('Invalid pricing amounts');
  return {
    subtotal: subtotalCents / 100,
    delivery_fee: baseDelivery / 100,
    distance_fee: distanceFee / 100,
    vendor_fee: vendorFee / 100,
    tax: tax / 100,
    tip: tip / 100,
    tip_percent: tipPercent,
    total: total / 100,
    policy,
  };
}
