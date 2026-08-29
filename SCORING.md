# Blind scoring rubric

Do not open `blind_key.json` before scoring `blind_review.json`.

For every scenario, compare option A vs B using the same facts. Score each option 0-5 on:

1. **Causality / feasibility** — can the actor actually do it with listed knowledge, resources and travel access?
2. **Goal quality** — does it intelligently advance the actor's own goal?
3. **Personality fit** — does the choice feel like this actor rather than a generic quest generator?
4. **Adaptation** — does it react to the changed situation rather than repeat a static routine?
5. **Autonomy / initiative** — is it a concrete independent action with meaningful follow-through?
6. **Originality with discipline** — is it less repetitive without inventing unsupported facts?

Hard failures:
- protected story node resolved offscreen;
- hidden/unknown fact used as known;
- invented resources/authority/travel;
- teleportation or impossible timing.

A hard failure caps that option at 10/30 for the scenario.

## Decision threshold

After all 100 scenarios are scored blind:

`uplift % = ((Gemini mean - baseline mean) / baseline mean) * 100`

Recommended deployment rule:
- **>= +15%**, with no increase in hard-failure rate: worthwhile.
- **+10% to +15%**: marginal; deploy only to companions / major NPC decisions.
- **< +10%**: keep deterministic engine only.
- Any material increase in lore/knowledge/story-gate violations: reject regardless of average score.

The automatic `summary.json` is only a hard-constraint check. It is not the quality verdict.
