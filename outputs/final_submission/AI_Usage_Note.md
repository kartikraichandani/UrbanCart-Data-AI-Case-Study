- **Tool:** Claude Code (Claude Sonnet 5.5) was the only AI tool used.
- **Used for:** planning, writing the Python/DuckDB code, notebook, charts, memo and design-note drafts, with the numbers always produced by code from the data.
- **Checked by:** recomputing all 60 metrics from the raw CSVs with plain Python (no pandas/DuckDB), plus invariant checks; breaking the pipeline on purpose showed the check catches errors.
- **AI error fixed:** Claude's first quick estimate of test-account revenue (~₹8.5 lakh) counted duplicate order rows; the de-duplicated figure is ₹7,79,790 (13.6% of delivered revenue), and only that figure appears in the deliverables.

