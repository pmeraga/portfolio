# ARC-AGI Agent Challenge

## The Task

You have a repo with an LLM agent that attempts to solve ARC-AGI puzzles. ARC puzzles show input-to-output grid transformations as examples, and the agent must predict the output for a new test input.

The agent currently scores poorly. Your job: **make it score as high as possible.**

## Setup (5 min)

```bash
git clone <repo-url>
cd arc-agent-interview
npm install
cp .env.example .env
# Add your API key to .env
```

Verify it runs:

```bash
npx tsx src/index.ts
```

You should see the agent attempt all 20 puzzles and print a score.

Inspect a specific puzzle in detail:

```bash
npx tsx src/index.ts --puzzle 003 -v
```

## Rules

- **Use any AI coding tool** (Cursor, Copilot, Claude Code, etc.) but restrict your coding assistant to a cheap/fast model (e.g., GPT-4o-mini, Claude Haiku, Gemini Flash). We want to see your engineering judgment, not your AI assistant's.
- The **puzzle-solving agent** itself uses a frontier model (GPT-5.4 or Claude Opus 4.6) -- failures are due to the harness, not the model.
- You can **modify any file** in the repo
- You can **add new files**, tools, or dependencies
- The eval harness scores your agent -- **higher is better**
- Both exact match count and cell accuracy matter

## What we're evaluating

- How you **navigate and understand** unfamiliar code
- How you **debug AI system failures** (why does the agent get things wrong?)
- Your **architectural decisions** for improving the agent
- How you **communicate your reasoning** as you work

## Structure

- **45 minutes** coding (you drive, we observe and ask questions)
- **15 minutes** discussion (architecture, trade-offs, what you'd do with more time)

## Tips

- Start by understanding what the agent does now and why it fails
- Use `--verbose` mode to see what the LLM actually produces
- Focus on one puzzle first before trying to improve everything
- There's no perfect score -- we care about your approach, not the final number
