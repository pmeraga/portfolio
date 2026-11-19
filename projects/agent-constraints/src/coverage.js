import { dietaryEvidence, normalizeRestriction } from "./dietary.js";
import { pricingPolicy } from "./pricing.js";

// Each group represents distinct diners. A combined group requires every tag.
export function validateConstraints(value, office) {
  const c = { groups: [], notes: office.dietary_notes, confirmed: false, ...value, headcount: office.headcount, budget_per_person: office.budget_per_person };
  if (!Number.isSafeInteger(c.headcount) || c.headcount < 1) throw new Error('Headcount must be a positive integer');
  if (!Number.isFinite(c.budget_per_person) || c.budget_per_person < 0) throw new Error('Budget must be a nonnegative number');
  c.tip_percent = value?.tip_percent ?? 10;
  if (!Number.isFinite(c.tip_percent) || c.tip_percent < 0 || c.tip_percent > 100) throw new Error("Tip must be between 0% and 100%");
  c.pricing_policy = pricingPolicy();
  if (!Array.isArray(c.groups) || c.groups.length > 100) throw new Error('Invalid dietary groups');
  for (const g of c.groups) {
    if (!Number.isSafeInteger(g.count) || g.count < 1 || !Array.isArray(g.tags) || !g.tags.length || g.tags.some(t => typeof t !== 'string' || !t.trim())) throw new Error('Each dietary group needs a positive count and restrictions');
    g.tags = [...new Set(g.tags.map(normalizeRestriction))];
  }
  if (c.groups.reduce((s, g) => s + g.count, 0) > c.headcount) throw new Error('Dietary groups exceed headcount; count each person once');
  return { ...c, notes: String(c.notes ?? ''), confirmed: c.confirmed === true };
}

export function assessOrder(lines, total, constraints) {
  if (!constraints) return { status: 'needs-review', warnings: ['No saved requirements for this order'], groups: [] };
  const c = constraints;
  if (!Number.isSafeInteger(c.headcount) || c.headcount < 1 || !Array.isArray(c.groups)) throw new Error('Invalid coverage constraints');
  if (!Number.isFinite(total) || total < 0) throw new Error('Invalid order total');
  for (const l of lines) {
    if (!Number.isSafeInteger(l.quantity) || l.quantity < 1 || !Number.isSafeInteger(l.serves) || l.serves < 1 || !Number.isSafeInteger(l.quantity * l.serves))
      throw new Error('Portion quantities and serving sizes must be positive safe integers');
    if (l.tags != null && typeof l.tags !== 'string') throw new Error('Menu tags must be a comma-separated string');
  }
  const groups = c.groups.map(g => {
    if (!Number.isSafeInteger(g.count) || g.count < 1 || !Array.isArray(g.tags) || !g.tags.length || g.tags.some(t => typeof t !== 'string' || !t.trim())) throw new Error('Invalid dietary group');
    return { ...g, tags: [...new Set(g.tags.map(normalizeRestriction))] };
  });
  if (groups.reduce((s, g) => s + g.count, 0) > c.headcount) throw new Error('Dietary groups exceed headcount');
  const unrestricted = c.headcount - groups.reduce((s, g) => s + g.count, 0);
  if (unrestricted) groups.push({ tags: [], count: unrestricted });
  // Maximum flow allocates shared portions without double counting or greedy mismatches.
  const source = 0, firstLine = 1, firstGroup = firstLine + lines.length, sink = firstGroup + groups.length;
  const edges = Array.from({ length: sink + 1 }, () => []);
  function edge(a, b, cap) {
    const f = { to: b, cap, initial: cap, reverse: edges[b].length };
    edges[a].push(f); edges[b].push({ to: a, cap: 0, initial: 0, reverse: edges[a].length - 1 });
    return f;
  }
  const allocations = groups.map(() => []);
  lines.forEach((line, i) => {
    edge(source, firstLine + i, line.quantity * line.serves);
    const tags = dietaryEvidence(line.tags ?? "");
    groups.forEach((g, j) => {
      if (g.tags.every(t => tags.has(t))) allocations[j].push({ line, edge: edge(firstLine + i, firstGroup + j, c.headcount) });
    });
  });
  groups.forEach((g, j) => edge(firstGroup + j, sink, g.count));
  while (true) {
    const visited = new Set();
    function send(v, amount) {
      if (v === sink) return amount;
      visited.add(v);
      for (const e of edges[v]) if (e.cap > 0 && !visited.has(e.to)) {
        const flow = send(e.to, Math.min(amount, e.cap));
        if (flow) { e.cap -= flow; edges[e.to][e.reverse].cap += flow; return flow; }
      }
      return 0;
    }
    if (!send(source, c.headcount)) break;
  }
  const result = groups.map((g, j) => {
    const items = allocations[j].map(({ line, edge: e }) => ({ name: line.name, portions: e.initial - e.cap })).filter(i => i.portions);
    return { ...g, covered: items.reduce((s, i) => s + i.portions, 0), items };
  });
  const portions = lines.reduce((s, l) => s + l.quantity * l.serves, 0);
  const warnings = [];
  if (!c.confirmed) warnings.push('Dietary groups have not been confirmed for this order. Review the saved notes.');
  if (result.some(g => g.covered < g.count)) warnings.push('Some diners do not have enough verified portions.');
  const budget = c.budget_per_person == null ? null : c.headcount * Math.round(c.budget_per_person * 100) / 100;
  if (budget != null && Math.round(total * 100) > Math.round(budget * 100)) warnings.push('Delivered total exceeds the budget.');
  return { status: warnings.length ? 'needs-review' : 'covered', constraints: c, groups: result, total, cost_per_person: total / c.headcount, budget, portions, surplus: Math.max(0, portions - c.headcount), warnings };
}

// Compare currency in cents, including every fee in the priced total.
export function enforceBudget(total, constraints) {
  const headcount = constraints?.headcount;
  const perPerson = constraints?.budget_per_person;
  if (!Number.isSafeInteger(headcount) || headcount < 1 || !Number.isFinite(perPerson) || perPerson < 0)
    throw new Error("Set a valid headcount and budget per person in Team settings before ordering.");
  const budgetCents = Math.round(perPerson * 100) * headcount;
  const totalCents = Math.round(total * 100);
  if (!Number.isSafeInteger(budgetCents) || !Number.isSafeInteger(totalCents) || totalCents < 0)
    throw new Error("Invalid order total or budget.");
  if (totalCents > budgetCents)
    throw new Error(`Order total $${(totalCents / 100).toFixed(2)} exceeds the firm budget of $${(budgetCents / 100).toFixed(2)} for ${headcount} people. Reduce the cost or try another restaurant; do not reduce meal coverage. Change Team settings to authorize a different budget.`);
  return { budget: budgetCents / 100, cost_per_person: total / headcount, budget_remaining: (budgetCents - totalCents) / 100 };
}
