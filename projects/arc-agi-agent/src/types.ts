/** A 2D grid of integers 0-9. 0 = black/empty, 1-9 = colors. */
export type Grid = number[][];

/** A single input/output demonstration pair. */
export type Example = {
  input: Grid;
  output: Grid;
};

/** An ARC-AGI task with training examples and test cases. */
export type ArcTask = {
  id: string;
  train: Example[];
  test: { input: Grid; output: Grid }[];
};

/** Result of running the agent on one task. */
export type AgentResult = {
  taskId: string;
  predicted: Grid | null;
  expected: Grid;
  correct: boolean;
  cellAccuracy: number;
  reasoning?: string;
};

/** A chat message for the LLM. */
export type LLMMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};
