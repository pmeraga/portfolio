# Portfolio import notes

The existing research notebooks and embedded systems folders are preserved. New projects are standalone snapshots under `projects/`; nested Git history is not imported.

| Folder | Source |
| --- | --- |
| `projects/square-kettle-backtester` | `Desktop/square kettle/SweTakeHome` |
| `projects/arc-agi-agent` | `Endex/arc-interview-pranav-meraga` |
| `projects/mercor-candidate-search` | `Downloads/mercor_2` |
| `projects/sf-code-intelligence` | `Downloads/interview-questions-main/sf-code-intelligence` |
| `projects/macrobase-aml` | `Desktop/dummy/macrobase_pipeline.zip` and the accompanying AML technical write-up in Downloads |

The HECTUR robotics website is linked from the main README.

## Packaging

- Source code, project documentation, dependencies, tests, fixtures, and the supplied Square Kettle sample data are included.
- Credentials, local `.env` files, nested Git repositories, virtual environments, package caches, editor state, and the generated Salesforce database are excluded.
- Mercor runtime results and caches are excluded because they contain candidate records and service responses. The original documentation retains its historical score table; the evaluation criteria spreadsheet is included.
- The ARC source folder lacked `package.json`. It was reconstructed from the existing lockfile's root dependency metadata, with ES module mode and start/typecheck scripts.
- The AML archive is expanded for browsing. Its original run log is retained and the technical write-up is transcribed into Markdown without correcting its historical claims. The project README describes the interpretation limits.

These are assessment/research snapshots. Original starter instructions and third-party attribution are retained; the portfolio descriptions distinguish assessment work and team contributions.

## Import validation

- Salesforce code intelligence: 21 tests passed on the imported copy.
- ARC agent: locked dependency installation and `tsc --noEmit` passed.
- All 44 imported Python source files parsed successfully.
- Relative links in the new portfolio documentation resolve locally.
- Imported files were checked for known local API credentials and common token/private-key patterns; none were found.
- Original source formatting is preserved, including pre-existing whitespace warnings. Newly authored portfolio documents pass Git whitespace checks.
- Live Mercor/ARC model calls, a full AML dataset run, and the full Square Kettle backtesting suite were not executed during this import.
