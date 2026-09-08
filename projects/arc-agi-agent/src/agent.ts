import { chat } from "./llm.js";
import { gridToText, parseGridFromText } from "./grid.js";
import type { ArcTask, Grid, LLMMessage } from "./types.js";

const SYSTEM_PROMPT = `You are a puzzle solver for ARC-AGI tasks.

Puzzle semantics (same as the JSON puzzle format in this repo):
- Training pairs are input/output grids: 2D matrices of integers 0-9 (0 = empty/black, 1-9 = colors).
- You must predict the test output grid with the same value range and a valid height x width for the pattern.

Output rules (critical):
- Reply with ONLY the predicted test output grid. No analysis, no headings, no markdown, no code fences.
- Use the same text layout as the examples in this chat: one row per line, space-separated digits 0-9 only (equivalent to one row of the JSON "output" array).
- Alternatively you may output a single JSON 2D array of integers 0-9 only (no wrapper object).
- Do not include words, punctuation, or extra blank lines before or after the grid.`;

export async function solveTask(task: ArcTask): Promise<{
  predicted: Grid | null;
  reasoning?: string;
}> {
  const prompt = buildPrompt(task);

  const messages: LLMMessage[] = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: prompt },
  ];

  const response = await chat(messages);
  const predicted = parseGridFromText(response);

  return {
    predicted,
    reasoning: response,
  };
}

function buildPrompt(task: ArcTask): string {
  let prompt = "Here are some example input/output pairs:\n\n";

  for (let i = 0; i < task.train.length; i++) {
    prompt += `Example ${i + 1}:\n`;
    prompt += `Input:\n${gridToText(task.train[i].input)}\n\n`;
    prompt += `Output:\n${gridToText(task.train[i].output)}\n\n`;
  }

  prompt += `Now solve this:\n`;
  prompt += `Input:\n${gridToText(task.test[0].input)}\n\n`;
  prompt += `What is the output?\n\n`;
  prompt += `Output format (must match puzzle semantics: 2D grid of integers 0-9, same cell meaning as in the JSON puzzle file "output" arrays):\n`;
  prompt += `- Print ONLY the predicted test output: one row per line, each cell a single digit 0-9 separated by one space (same layout as the Input/Output blocks above).\n`;
  prompt += `- Or output only a JSON 2D array like [[0,1],[2,3]] with no other text.\n`;
  prompt += `- Do not wrap in markdown fences; do not print anything else (no "Here is", no reasoning).`;

  return prompt;
}
