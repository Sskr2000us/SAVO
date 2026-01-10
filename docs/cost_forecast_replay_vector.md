# Cost Forecast (10× / 100×) — Event Replay + Vector Infra

This is an order-of-magnitude planning model. Plug in your real volumes to produce $/month estimates.

## Inputs
Let:
- $U$ = active users
- $E_u$ = events per user per day (event_log)
- $R$ = replay runs per day (ops + experiments)
- $W$ = replay window length in days
- $T$ = entities embedded per day (ingredients + pantry states + recipes + intents)
- $d$ = embedding dimension (provider-dependent)

## Event Storage
- Events/day: $E = U \cdot E_u$
- Events/month: $E_m \approx 30E$
- Storage/month: $S \approx E_m \cdot \text{avg_event_bytes}$

10× scenario: multiply $U$ and/or $E_u$ by 10.
100× scenario: multiply by 100.

## Replay Compute
Replay scans the event stream for a user and time window.
- Events scanned/run: $\approx E_u \cdot W$
- Total events scanned/day: $R \cdot E_u \cdot W$

Key drivers:
- Larger $W$ and higher $R$ scale linearly.
- DB read cost dominates if replay pulls raw rows rather than aggregated summaries.

Mitigations:
- Narrow windows (use bounded `from_ts/to_ts`)
- Store append-only replay outputs (`replay_runs`, `replay_inventory_snapshots`)
- Cache intermediate snapshots by window boundaries

## Embedding Generation
Embedding cost scales with tokens (text length) and number of embeds.
- Embeds/day: $T$
- Tokens/day: $\approx T \cdot \text{avg_tokens_per_entity}$

10×: $10T$ embeds/day.
100×: $100T$ embeds/day.

Mitigations:
- Only embed on event-driven changes (no cron)
- Deduplicate by entity signature + embedding_version
- Batch embedding calls

## Vector DB Storage
Vector storage roughly:
- Vectors stored: $V$
- Bytes/vector: $\approx 4d$ (float32) + metadata
- Total: $\approx V \cdot (4d + \text{metadata_bytes})$

## Vector Query Cost
Queries/day depends on feature adoption:
- pantry/ingredient search queries/day
- recipe recommendation queries/day
- substitution queries/day

Mitigations:
- Entry thresholds: keep non-vector path until scale justifies
- Cache top queries per user / household

## Monitoring Overhead
Track:
- replay failures
- vector sync queue lag
- embedding generation errors
- p95 latency for vector-enabled endpoints

Costs are typically small relative to embedding + vector infra, but increase at 100× scale.

## Recommendation
Treat 10× as a stress test of event volume + replay correctness, and 100× as the point where:
- you must batch embeddings,
- you must partition vector namespaces,
- and you must formalize SLAs/alerting for queue lag.
