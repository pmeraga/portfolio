import chalk from "chalk";
import type { Grid } from "./types.js";

/** ARC color palette mapped to chalk terminal colors. */
const COLOR_MAP: Record<number, (text: string) => string> = {
  0: chalk.bgBlack.gray,
  1: chalk.bgBlue.white,
  2: chalk.bgRed.white,
  3: chalk.bgGreen.black,
  4: chalk.bgYellow.black,
  5: chalk.bgGray.white,
  6: chalk.bgMagenta.white,
  7: chalk.bgHex("#FF8C00").black,
  8: chalk.bgCyan.black,
  9: chalk.bgHex("#8B0000").white,
};

/** Render a grid with colored blocks in the terminal. */
export function displayGrid(grid: Grid): string {
  return grid
    .map((row) =>
      row
        .map((cell) => {
          const colorFn = COLOR_MAP[cell] ?? chalk.bgWhite.black;
          return colorFn(` ${cell} `);
        })
        .join("")
    )
    .join("\n");
}

/** Compare two grids cell-by-cell. Returns match status, accuracy, and a visual diff. */
export function compareGrids(
  predicted: Grid,
  expected: Grid
): { match: boolean; cellAccuracy: number; diff: string } {
  if (predicted.length !== expected.length) {
    return {
      match: false,
      cellAccuracy: 0,
      diff: `Row count mismatch: got ${predicted.length}, expected ${expected.length}`,
    };
  }

  let totalCells = 0;
  let correctCells = 0;
  const diffLines: string[] = [];

  for (let r = 0; r < expected.length; r++) {
    if (!predicted[r] || predicted[r].length !== expected[r].length) {
      return {
        match: false,
        cellAccuracy: 0,
        diff: `Row ${r} length mismatch: got ${predicted[r]?.length ?? 0}, expected ${expected[r].length}`,
      };
    }

    const diffRow: string[] = [];
    for (let c = 0; c < expected[r].length; c++) {
      totalCells++;
      if (predicted[r][c] === expected[r][c]) {
        correctCells++;
        diffRow.push(chalk.green(` ${predicted[r][c]} `));
      } else {
        diffRow.push(
          chalk.bgRed.white(` ${predicted[r][c]}>${expected[r][c]} `)
        );
      }
    }
    diffLines.push(diffRow.join(""));
  }

  return {
    match: totalCells === correctCells,
    cellAccuracy: totalCells > 0 ? correctCells / totalCells : 0,
    diff: diffLines.join("\n"),
  };
}

/** Convert a grid to a text string. */
export function gridToText(grid: Grid): string {
  return grid.map((row) => row.join(" ")).join("\n");
}

/** Remove markdown code-fence lines (``` or ```lang). Keeps fenced inner content. */
export function stripMarkdownFences(text: string): string {
  return text
    .split("\n")
    .filter((line) => !/^\s*```[\w]*\s*$/.test(line))
    .join("\n");
}

/** True if the trimmed line is only space-separated single digits 0-9 (ARC row shape). */
export function isArcGridRow(line: string): boolean {
  const t = line.trim();
  if (!t) return false;
  return /^\d(\s+\d)*$/.test(t);
}

function rowFromArcLine(line: string): number[] {
  return line.trim().split(/\s+/).map(Number);
}

function isValidGrid(value: unknown): value is Grid {
  if (!Array.isArray(value) || value.length === 0) return false;
  const rows = value as unknown[];
  if (!rows.every((row) => Array.isArray(row) && row.length > 0)) {
    return false;
  }
  const width = (rows[0] as unknown[]).length;
  for (const row of rows) {
    const r = row as unknown[];
    if (r.length !== width) return false;
    for (const cell of r) {
      if (
        typeof cell !== "number" ||
        !Number.isInteger(cell) ||
        cell < 0 ||
        cell > 9
      ) {
        return false;
      }
    }
  }
  return true;
}

/** Extract top-level bracket spans `[` … `]` using depth counting (no string escape handling). */
export function extractTopLevelJsonArrays(text: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let start = -1;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === "[") {
      if (depth === 0) start = i;
      depth++;
    } else if (ch === "]") {
      depth--;
      if (depth === 0 && start !== -1) {
        out.push(text.slice(start, i + 1));
        start = -1;
      }
      if (depth < 0) depth = 0;
    }
  }
  return out;
}

function tryParseJsonGrid(text: string): Grid | null {
  const trimmed = text.trim();
  if (trimmed.startsWith("[")) {
    try {
      const parsed: unknown = JSON.parse(trimmed);
      if (isValidGrid(parsed)) return parsed;
    } catch {
      /* fall through */
    }
  }

  const candidates = extractTopLevelJsonArrays(text);
  for (let i = candidates.length - 1; i >= 0; i--) {
    try {
      const parsed: unknown = JSON.parse(candidates[i]);
      if (isValidGrid(parsed)) return parsed;
    } catch {
      /* continue */
    }
  }
  return null;
}

/** Collect maximal contiguous runs of strict ARC rows with uniform width. */
export function extractNumericGridBlocks(text: string): Grid[] {
  const normalized = stripMarkdownFences(text);
  const lines = normalized.split("\n");
  const blocks: Grid[] = [];
  let buf: number[][] = [];

  const flush = (): void => {
    if (buf.length > 0) {
      blocks.push(buf.map((r) => [...r]));
      buf = [];
    }
  };

  for (const line of lines) {
    if (isArcGridRow(line)) {
      const row = rowFromArcLine(line);
      if (buf.length === 0) {
        buf.push(row);
      } else if (row.length === buf[0].length) {
        buf.push(row);
      } else {
        flush();
        buf.push(row);
      }
    } else {
      flush();
    }
  }
  flush();
  return blocks;
}

/**
 * Pick the best contiguous numeric block: largest area (rows × cols);
 * on a tie, prefer the last block in the document (answer after rationale).
 */
export function pickBestNumericGridBlock(blocks: Grid[]): Grid | null {
  if (blocks.length === 0) return null;
  let bestIdx = 0;
  let bestArea = blocks[0].length * blocks[0][0].length;
  for (let i = 1; i < blocks.length; i++) {
    const area = blocks[i].length * blocks[i][0].length;
    if (area > bestArea) {
      bestArea = area;
      bestIdx = i;
    } else if (area === bestArea) {
      bestIdx = i;
    }
  }
  return blocks[bestIdx];
}

export function extractBestNumericGridBlock(text: string): Grid | null {
  return pickBestNumericGridBlock(extractNumericGridBlocks(text));
}

/**
 * Parse a grid from LLM text output.
 * Tries valid 2D JSON grids first, then strict space-separated ARC rows
 * (ignores prose lines that merely contain digits).
 */
export function parseGridFromText(text: string): Grid | null {
  const fromJson = tryParseJsonGrid(text);
  if (fromJson) return fromJson;

  return extractBestNumericGridBlock(text);
}
