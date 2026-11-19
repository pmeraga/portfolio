// Keep vocabulary and implications in data; allocation stays restriction-agnostic.
// Unknown restrictions require an exact explicit menu tag. Never infer from dish names.
const aliases = {
  'gluten free': 'gluten-free', gf: 'gluten-free',
  'no pork': 'pork-free', 'no-pork': 'pork-free', "don't eat pork": 'pork-free',
  'dairy free': 'dairy-free', 'nut free': 'nut-free',
};
const implications = {
  vegan: ['vegetarian', 'dairy-free'],
  vegetarian: ['pork-free'],
};
export function normalizeRestriction(tag) {
  const normalized = tag.trim().toLowerCase();
  return Object.hasOwn(aliases, normalized) ? aliases[normalized] : normalized;
}
export function dietaryEvidence(tags = '') {
  const evidence = new Set(tags.split(',').map(normalizeRestriction).filter(Boolean));
  for (const tag of evidence) for (const implied of Object.hasOwn(implications, tag) ? implications[tag] : []) evidence.add(implied);
  return evidence;
}
