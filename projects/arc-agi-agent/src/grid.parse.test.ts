import assert from "node:assert/strict";
import test from "node:test";
import {
  extractBestNumericGridBlock,
  extractNumericGridBlocks,
  parseGridFromText,
  stripMarkdownFences,
} from "./grid.js";

test("stripMarkdownFences removes fence lines only", () => {
  const input = "before\n```\n0 1\n```\nafter";
  assert.equal(stripMarkdownFences(input), "before\n0 1\nafter");
});

test("parseGridFromText: chatty reasoning + fenced grid (0a938d79-style)", () => {
  const completion = `Let me analyze the pattern from the examples.

In Examples 1 and 2, the two points share the same row or column orientation - they define vertical stripes.

\`\`\`
0 0 0 0 0 3 0 0 0 0 4 0 0 0 0 3 0 0 0 0 4 0 0 0 0 3 0
0 0 0 0 0 3 0 0 0 0 4 0 0 0 0 3 0 0 0 0 4 0 0 0 0 3 0
0 0 0 0 0 3 0 0 0 0 4 0 0 0 0 3 0 0 0 0 4 0 0 0 0 3 0
\`\`\`
`;
  const grid = parseGridFromText(completion);
  assert.ok(grid);
  assert.equal(grid!.length, 3);
  assert.equal(grid![0].length, 27);
  assert.deepEqual(grid![0].slice(5, 7), [3, 0]);
});

test("parseGridFromText: plain grid only (2dee498d-style)", () => {
  const completion = `0 2 0 4 4
2 2 0 4 4
0 2 2 2 0
1 1 0 2 2
1 1 0 2 0`;
  const grid = parseGridFromText(completion);
  assert.ok(grid);
  assert.equal(grid!.length, 5);
  assert.equal(grid![0].length, 5);
  assert.deepEqual(grid![0], [0, 2, 0, 4, 4]);
});

test("parseGridFromText: JSON-only 2D array", () => {
  const completion = "[[0,1,2],[3,4,5]]";
  const grid = parseGridFromText(completion);
  assert.ok(grid);
  assert.deepEqual(grid, [
    [0, 1, 2],
    [3, 4, 5],
  ]);
});

test("extractNumericGridBlocks: two same-sized blocks prefers larger area, tie last", () => {
  const text = `2 2
2 2

ignored words 1 2

9 9 9
9 9 9
9 9 9
`;
  const blocks = extractNumericGridBlocks(text);
  assert.ok(blocks.length >= 2);
  const best = extractBestNumericGridBlock(text);
  assert.ok(best);
  assert.equal(best!.length, 3);
  assert.equal(best![0].length, 3);
  assert.deepEqual(best![0], [9, 9, 9]);
});
