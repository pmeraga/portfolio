import { readdir, readFile } from "fs/promises";
import { join } from "path";
import chalk from "chalk";
import type { ArcTask, AgentResult } from "./types.js";
import { solveTask } from "./agent.js";
import { displayGrid, compareGrids } from "./grid.js";
import { getTokenUsage, resetTokenUsage } from "./llm.js";

/** Load all puzzle JSON files from a directory. */
export async function loadPuzzles(dir: string): Promise<ArcTask[]> {
  const files = await readdir(dir);
  const jsonFiles = files.filter((f) => f.endsWith(".json")).sort();

  const puzzles: ArcTask[] = [];
  for (const file of jsonFiles) {
    const content = await readFile(join(dir, file), "utf-8");
    const data = JSON.parse(content);
    puzzles.push({
      id: file.replace(".json", ""),
      train: data.train,
      test: data.test,
    });
  }

  return puzzles;
}

/** Run the agent on puzzles and print results. */
export async function runEval(options: {
  puzzleDir: string;
  puzzleId?: string;
  verbose?: boolean;
}): Promise<void> {
  const puzzles = await loadPuzzles(options.puzzleDir);

  const filtered = options.puzzleId
    ? puzzles.filter((p) => p.id === options.puzzleId)
    : puzzles;

  if (filtered.length === 0) {
    console.log(
      chalk.red(
        `No puzzles found${options.puzzleId ? ` matching "${options.puzzleId}"` : ""}`
      )
    );
    return;
  }

  resetTokenUsage();
  const results: AgentResult[] = [];

  console.log(chalk.bold(`\nRunning ${filtered.length} puzzle(s)...\n`));

  for (const puzzle of filtered) {
    const testCase = puzzle.test[0];
    process.stdout.write(chalk.bold(`Puzzle ${puzzle.id}: `));

    if (options.verbose) {
      console.log();
      console.log(chalk.dim("  Train examples:"));
      for (let i = 0; i < puzzle.train.length; i++) {
        console.log(chalk.dim(`    Example ${i + 1} input:`));
        console.log(
          displayGrid(puzzle.train[i].input)
            .split("\n")
            .map((l) => "      " + l)
            .join("\n")
        );
        console.log(chalk.dim(`    Example ${i + 1} output:`));
        console.log(
          displayGrid(puzzle.train[i].output)
            .split("\n")
            .map((l) => "      " + l)
            .join("\n")
        );
        console.log();
      }
      console.log(chalk.dim("  Test input:"));
      console.log(
        displayGrid(testCase.input)
          .split("\n")
          .map((l) => "    " + l)
          .join("\n")
      );
      console.log();
    }

    try {
      const { predicted, reasoning } = await solveTask(puzzle);

      if (options.verbose && reasoning) {
        console.log(chalk.dim("  Agent output:"));
        console.log(
          chalk.dim(
            reasoning
              .split("\n")
              .map((l) => "    " + l)
              .join("\n")
          )
        );
        console.log();
      }

      if (!predicted) {
        console.log(chalk.red("FAIL") + chalk.dim(" (could not parse output)"));
        results.push({
          taskId: puzzle.id,
          predicted: null,
          expected: testCase.output,
          correct: false,
          cellAccuracy: 0,
        });
        continue;
      }

      const comparison = compareGrids(predicted, testCase.output);

      if (comparison.match) {
        console.log(chalk.green("PASS"));
      } else {
        console.log(
          chalk.red("FAIL") +
            chalk.dim(
              ` (${(comparison.cellAccuracy * 100).toFixed(0)}% cells correct)`
            )
        );
        if (options.verbose) {
          console.log(chalk.dim("  Diff (predicted>expected):"));
          console.log(
            comparison.diff
              .split("\n")
              .map((l) => "    " + l)
              .join("\n")
          );
        }
      }

      results.push({
        taskId: puzzle.id,
        predicted,
        expected: testCase.output,
        correct: comparison.match,
        cellAccuracy: comparison.cellAccuracy,
        reasoning,
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      console.log(chalk.red("ERROR") + chalk.dim(` (${msg})`));
      results.push({
        taskId: puzzle.id,
        predicted: null,
        expected: testCase.output,
        correct: false,
        cellAccuracy: 0,
      });
    }
  }

  // Print summary
  const correct = results.filter((r) => r.correct).length;
  const avgAccuracy =
    results.reduce((sum, r) => sum + r.cellAccuracy, 0) / results.length;
  const tokens = getTokenUsage();

  console.log(chalk.bold("\n════════════════════════════"));
  console.log(
    chalk.bold("Score: ") +
      chalk.bold(
        correct > 0 ? chalk.green(`${correct}`) : chalk.red(`${correct}`)
      ) +
      chalk.bold(`/${results.length}`) +
      chalk.dim(" correct")
  );
  console.log(
    chalk.bold("Cell accuracy: ") +
      chalk.bold(`${(avgAccuracy * 100).toFixed(1)}%`) +
      chalk.dim(" average")
  );
  console.log(
    chalk.bold("Tokens: ") +
      chalk.dim(
        `${(tokens.prompt + tokens.completion).toLocaleString()} total (${tokens.prompt.toLocaleString()} prompt, ${tokens.completion.toLocaleString()} completion)`
      )
  );
  console.log(chalk.bold("════════════════════════════\n"));
}
