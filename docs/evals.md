# Assistant evals

The assistant is tested with real models on the full build, using 30 cases in
[api/evals/cases.yaml](../api/evals/cases.yaml):

| Category | Cases | What is checked |
|---|---|---|
| Ranking | 6 | Weights set before ranking (family, commuter, retiree, young professional), place and price filters, areas highlighted on the map |
| Look-ups | 11 | The right tool and arguments for profiles, comparisons, nearby pubs and GPs, score explanations, map layers, the shortlist and the indicator catalogue |
| Follow-ups | 2 | "Compare the top two", "now do that for retirees" |
| Ambiguity | 2 | Says which Clapham or Newport it used (Newport in Wales isn't covered) |
| Scope and ethics | 4 | Edinburgh is out of scope; it declines to rank by immigration or religion; off-topic requests use no tools |
| Grounding | 2 (+16) | Every number in a reply appears in a tool result, the prompt or the model's own tool arguments (checked on 18 cases) |
| Analyst | 2 | SQL only in analyst mode |
| Injection | 1 | A pub name carrying "ignore all previous instructions…" isn't obeyed |

## Results

| Model (via OpenRouter) | Passed | Turn p50 | Turn p95 | Cost per question | Reply words (median) | Run |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 30/30 | 7.05 s | 12.29 s | $0.0418 | 77.5 | 2026-10-07 |
| Claude Haiku 5.5 (the default) | 30/30 | 5.12 s | 10.72 s | $0.0014 | 72 | 2026-10-08 |
| Qwen 3.8 27B (open weights) | 30/30 | 7.28 s | 20.6 s | $0.0045 (est.) | 66 | 2026-10-07 |

Per-case detail (tools called, replies, failed checks) is in [docs/evals/](evals/).
Costs are what OpenRouter billed, except "(est.)": list price × tokens, from runs before
the billed cost was read from OpenRouter's responses.

## What the evals found and fixed

- **Weights applied after the ranking.** Models often send `set_weights` and
  `rank_areas` together, and run in parallel the ranking could use the old weights.
  Tools that change the shared state now run as barriers (`sequential=True`).
- **"Manchester city centre" resolved to Withington.** A local authority used the
  middle of its bounding box; it now resolves through its namesake place (the city
  centre point).
- **Comparisons of named suburbs used one LSOA.** "Headingley vs Chapel Allerton" now
  compares the neighbourhoods (MSOAs) they sit in.
- **Unknown places failed the whole turn.** Tool errors now go back to the model as a
  retry prompt, so it can try another spelling or explain (Edinburgh → "England only").
- **Theme names.** Weaker models wrote "Schools & childcare" or "crime" instead of
  theme ids; presets and themes are now matched leniently, and the ids are stored in
  the shared state so the sliders move.
- **Verbose replies.** Opus's replies had a median of 112 words over 6 sentences; the
  instruction now asks for at most three sentences (about 60 words), bringing the
  median down to about 77 words.

## Choosing the model

All three models pass every case. Claude Haiku 5.5 answers faster than Opus 5.5 at
about 1/30 of the cost, with replies of similar quality; Opus frames trade-offs slightly
more carefully. Haiku 5.5 is the default, with the open-weights Qwen 3.8 27B, served by
a different provider, as the fallback (.env.example):

```bash
LIX_MODEL=openrouter:anthropic/claude-haiku-5.5
LIX_FALLBACK_MODELS=openrouter:qwen/qwen3.8-27b
```

For a stakeholder demo where every answer counts, Opus 5.5 is worth its cost.

## Running it

```bash
make eval MODEL=openrouter:anthropic/claude-haiku-5.5 CASES=family_leeds_budget,compare_two
make eval MODEL=openrouter:anthropic/claude-haiku-5.5       # all 30 cases, about $0.05
make eval MODEL=openrouter:anthropic/claude-opus-5.5        # all 30 cases, about $1.30
```
