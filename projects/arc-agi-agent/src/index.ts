import "dotenv/config";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { runEval } from "./eval.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
const verbose = args.includes("-v") || args.includes("--verbose");
const puzzleIdx = args.indexOf("--puzzle");
const puzzleId = puzzleIdx >= 0 ? args[puzzleIdx + 1] : undefined;

const puzzleDir = resolve(__dirname, "../puzzles/training");

runEval({ puzzleDir, puzzleId, verbose }).catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
