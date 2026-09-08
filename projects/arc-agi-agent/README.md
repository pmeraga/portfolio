# ARC-AGI Agent

**Portfolio context:** ARC interview challenge project. This snapshot includes the agent, CLI, evaluation harness, and training puzzles. The missing package manifest was restored from the supplied lockfile; use `npm ci` to install reproducibly.

An LLM-powered agent that attempts to solve [ARC-AGI](https://arcprize.org/) puzzles.

## What are ARC puzzles?

ARC (Abstraction and Reasoning Corpus) puzzles present input/output grid pairs as training examples. Each grid is a 2D matrix of integers 0-9, where 0 is black and 1-9 represent colors. The task: figure out the transformation pattern from the examples, then apply it to a new test input to predict the output.

Example: if the training examples show grids being horizontally flipped, you'd flip the test input to produce the answer.

## Setup

```bash
npm install
cp .env.example .env
# Set ANTHROPIC_API_KEY (for Claude) or OPENAI_API_KEY (for GPT) in .env
# Default models: claude-opus-4-6 / gpt-5.4
```

## Usage

```bash
# Run all 20 puzzles
npx tsx src/index.ts

# Run a single puzzle
npx tsx src/index.ts --puzzle 005

# Verbose mode (shows grids, LLM output, diffs)
npx tsx src/index.ts --puzzle 005 -v

# Combine flags
npx tsx src/index.ts --puzzle 012 --verbose
```

## Project Structure

```
src/
  index.ts    - CLI entry point
  eval.ts     - Evaluation harness (loads puzzles, runs agent, scores results)
  agent.ts    - The agent that solves puzzles
  llm.ts      - LLM client wrapper
  grid.ts     - Grid utilities (display, compare, parse)
  types.ts    - TypeScript type definitions
puzzles/
  training/   - 20 puzzle JSON files
```

## Puzzle Format

Each puzzle is a JSON file:

```json
{
  "train": [
    { "input": [[0, 1], [2, 0]], "output": [[0, 2], [1, 0]] },
    { "input": [[0, 3], [4, 0]], "output": [[0, 4], [3, 0]] }
  ],
  "test": [
    { "input": [[0, 5], [6, 0]], "output": [[0, 6], [5, 0]] }
  ]
}
```

- `train`: demonstration pairs showing the transformation
- `test`: the puzzle to solve (output is used for scoring)
- Grid values: 0 = black/empty, 1-9 = colors

### How this maps to the agent

Puzzle files use **JSON 2D arrays** as above. The harness loads them into memory, then [`agent.ts`](src/agent.ts) shows each grid to the model as **plain text**: one row per line, **space-separated integers 0-9** (same cell values as the nested arrays, same semantics as the JSON).

Your answer must be that same logical grid: either

- **Preferred:** space-separated rows, matching the `Input:` / `Output:` style in the prompt, or  
- **Also accepted:** a single valid JSON 2D array of integers 0-9 (same shape as `output` would be in the file).

Do not mix prose, markdown fences, or unrelated digits into the grid block—see [`grid.ts`](src/grid.ts) `parseGridFromText` for what the scorer parses.
