# Constraint Enforcement for Tool-calling Agents

Contributions to the supplied lunch-agent starter: dietary normalization, portion allocation, budget enforcement helpers, and itemized pricing. The original starter repository is https://github.com/nlemoff/lunch-agent. This snapshot contains the added constraint modules and their focused tests, rather than the full ordering application.

## Problem

A model can propose an order that sounds reasonable but exceeds the total budget or double-counts portions for people with overlapping dietary needs.

## Implementation

The application checks the budget before saving and again before placement. The included modules itemize charges, normalize explicit dietary evidence, and allocate portions across restriction groups. Unknown tags require evidence. Pricing policy and tip choice come from application settings.

## Evidence

The imported pricing and allocation tests include boundary cases, combined restrictions, insufficient portions, and 256 generated menus checked against an exhaustive matcher. This is contribution work on a supplied lunch-agent starter. The snapshot contains the constraint modules and their unit tests.

## Limits

Menu tags and serving counts are assumptions supplied to the application. They do not verify restaurant allergy handling. The pricing defaults are estimates. The full model loop and real-order integrations are outside this source snapshot.

## Run

Requires Node 22 or newer. No package installation or API key is needed.

```sh
npm test
```

The source snapshot contains the deterministic decision layer. Budget rechecks at order-placement time belong to the original application's server routes.

## Links

- [Constraint modules & tests](https://github.com/pmeraga/portfolio/tree/main/projects/agent-constraints)
