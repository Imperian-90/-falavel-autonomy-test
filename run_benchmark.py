#!/usr/bin/env python3
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
DELAY = float(os.environ.get("GEMINI_DELAY_SECONDS", "6.2"))
MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "7"))
SCENARIO_FILE = Path(os.environ.get("SCENARIO_FILE", "scenarios.json"))
OUT_DIR = Path(os.environ.get("OUT_DIR", "results"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is missing.", file=sys.stderr)
    sys.exit(2)

SYSTEM = """You are deciding one autonomous action for a simulated fantasy-world actor.
You are NOT the game master and you cannot invent world facts.
Your purpose is to choose a believable, useful action that follows the actor's personality, goal,
knowledge, resources, location, relationships, causality, and constraints.

Hard rules:
- Use only facts explicitly listed under known_facts.
- Do not infer hidden canon, secret motives, unknown geography, or magical explanations.
- Do not create resources, authority, money, troops, contacts, equipment, or travel access.
- Do not teleport.
- A protected unresolved matter may be prepared for, investigated around, or reacted to, but not irreversibly resolved without required participation.
- The actor may change plans when new evidence makes that rational.
- Waiting is valid only when it is genuinely the best action.
- Prefer specific action over vague prose.
- Return only the requested JSON object.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "rationale": {"type": "string"},
        "knowledge_indices": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "resource_indices": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "new_assumptions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "moderate", "high"],
        },
        "waits": {"type": "boolean"},
        "protected_matter_action": {
            "type": "string",
            "enum": ["none", "prepare", "resolve"],
        },
        "expected_world_effect": {"type": "string"},
    },
    "required": [
        "intent",
        "steps",
        "rationale",
        "knowledge_indices",
        "resource_indices",
        "new_assumptions",
        "risk_level",
        "waits",
        "protected_matter_action",
        "expected_world_effect",
    ],
    "additionalProperties": False,
}

def scenario_prompt(s):
    known = "\n".join(f"{i+1}. {v}" for i, v in enumerate(s["known_facts"]))
    resources = "\n".join(f"{i+1}. {v}" for i, v in enumerate(s["resources"]))
    constraints = "\n".join(f"- {v}" for v in s["constraints"])
    return f"""SCENARIO {s['id']}

Role: {s['role']}
Personality: {", ".join(s['personality'])}
Current goal: {s['goal']}
Urgency (0-10): {s['urgency']}
Current location: {s['location']}
Reachable locations: {", ".join(s['reachable_locations'])}
Relationships: {json.dumps(s['relationships'], ensure_ascii=False)}

Known facts (reference these by 1-based index):
{known}

Available resources (reference these by 1-based index):
{resources}

Constraints:
{constraints}

Choose what this actor independently does next.
The intent should be one concrete sentence. Steps are the immediate execution plan.
If you need to assume a fact not supplied, list it in new_assumptions instead of silently treating it as true.
"""

def request_gemini(s):
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(MODEL, safe="")
        + ":generateContent?key="
        + urllib.parse.quote(API_KEY, safe="")
    )
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": scenario_prompt(s)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": RESPONSE_SCHEMA,
            "maxOutputTokens": 900,
        },
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            candidates = raw.get("candidates") or []
            if not candidates:
                raise RuntimeError(f"No candidates: {json.dumps(raw)[:800]}")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
            if not text:
                raise RuntimeError(f"No response text: {json.dumps(raw)[:800]}")
            parsed = json.loads(text)
            return {
                "decision": parsed,
                "model_version": raw.get("modelVersion"),
                "usage": raw.get("usageMetadata", {}),
                "response_id": raw.get("responseId"),
            }
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", "replace")
            last_err = f"HTTP {e.code}: {payload[:1000]}"
            if e.code not in (429, 500, 502, 503, 504) or attempt >= MAX_RETRIES:
                raise RuntimeError(last_err)
            retry_after = e.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                sleep_s = float(retry_after)
            else:
                sleep_s = min(60.0, (2 ** attempt) * 2.0 + random.random())
            print(f"Retry {attempt+1}/{MAX_RETRIES} after {sleep_s:.1f}s: {last_err[:140]}")
            time.sleep(sleep_s)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as e:
            last_err = repr(e)
            if attempt >= MAX_RETRIES:
                raise
            sleep_s = min(45.0, (2 ** attempt) * 1.5 + random.random())
            print(f"Retry {attempt+1}/{MAX_RETRIES} after {sleep_s:.1f}s: {last_err[:140]}")
            time.sleep(sleep_s)
    raise RuntimeError(last_err or "Unknown Gemini error")

def auto_validate(s, d):
    problems = []
    kmax = len(s["known_facts"])
    rmax = len(s["resources"])
    for idx in d.get("knowledge_indices", []):
        if not isinstance(idx, int) or idx < 1 or idx > kmax:
            problems.append(f"invalid_knowledge_index:{idx}")
    for idx in d.get("resource_indices", []):
        if not isinstance(idx, int) or idx < 1 or idx > rmax:
            problems.append(f"invalid_resource_index:{idx}")
    if d.get("new_assumptions"):
        problems.append("unsupported_assumptions")
    if s.get("twist") == "protected_story_gate" and d.get("protected_matter_action") == "resolve":
        problems.append("protected_gate_violation")
    if s.get("urgency", 0) >= 7 and d.get("waits") is True:
        problems.append("high_urgency_wait")
    blob = json.dumps(d, ensure_ascii=False).lower()
    for hidden in s.get("evaluation_hidden_facts", []):
        h = hidden.lower().strip()
        if len(h) >= 20 and h in blob:
            problems.append("hidden_fact_leak")
    return {
        "valid": not any(
            p.startswith("invalid_")
            or p in ("protected_gate_violation", "hidden_fact_leak")
            for p in problems
        ),
        "problems": problems,
        "assumption_count": len(d.get("new_assumptions", [])),
    }

def blind_pair(s, gemini_decision, rng):
    baseline = {
        "intent": s["deterministic_baseline"],
        "source_format": "deterministic_baseline",
    }
    gemini = {
        "intent": gemini_decision.get("intent", ""),
        "steps": gemini_decision.get("steps", []),
        "rationale": gemini_decision.get("rationale", ""),
        "expected_world_effect": gemini_decision.get("expected_world_effect", ""),
        "source_format": "agent_decision",
    }
    if rng.random() < 0.5:
        return {"A": baseline, "B": gemini}, {"A": "baseline", "B": "gemini"}
    return {"A": gemini, "B": baseline}, {"A": "gemini", "B": "baseline"}

def main():
    scenarios = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))
    if len(scenarios) != 100:
        print(f"WARNING: expected 100 scenarios, found {len(scenarios)}")

    results = []
    blind = []
    key = []
    rng = random.Random(20260829)

    for i, s in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] {s['id']} {s['role']} / {s['twist']}", flush=True)
        try:
            got = request_gemini(s)
            d = got["decision"]
            validation = auto_validate(s, d)
            row = {
                "scenario_id": s["id"],
                "role": s["role"],
                "twist": s["twist"],
                "urgency": s["urgency"],
                "baseline": s["deterministic_baseline"],
                "gemini": d,
                "validation": validation,
                "model": MODEL,
                "model_version": got.get("model_version"),
                "usage": got.get("usage", {}),
            }
            pair, pair_key = blind_pair(s, d, rng)
            blind.append({
                "scenario_id": s["id"],
                "role": s["role"],
                "twist": s["twist"],
                "urgency": s["urgency"],
                "personality": s["personality"],
                "goal": s["goal"],
                "known_facts": s["known_facts"],
                "resources": s["resources"],
                "constraints": s["constraints"],
                **pair,
            })
            key.append({"scenario_id": s["id"], **pair_key})
            results.append(row)
        except Exception as e:
            print(f"ERROR on {s['id']}: {e}", file=sys.stderr, flush=True)
            results.append({
                "scenario_id": s["id"],
                "role": s["role"],
                "twist": s["twist"],
                "urgency": s["urgency"],
                "baseline": s["deterministic_baseline"],
                "error": str(e),
                "model": MODEL,
            })
        if i < len(scenarios):
            time.sleep(DELAY)

    ok = [r for r in results if "gemini" in r]
    invalid = [r for r in ok if not r["validation"]["valid"]]
    assumption_cases = [r for r in ok if r["validation"]["assumption_count"] > 0]
    gate_violations = [r for r in ok if "protected_gate_violation" in r["validation"]["problems"]]
    hidden_leaks = [r for r in ok if "hidden_fact_leak" in r["validation"]["problems"]]
    high_waits = [r for r in ok if "high_urgency_wait" in r["validation"]["problems"]]

    summary = {
        "model": MODEL,
        "requested_scenarios": len(scenarios),
        "completed": len(ok),
        "errors": len(results) - len(ok),
        "auto_valid": len(ok) - len(invalid),
        "auto_invalid": len(invalid),
        "unsupported_assumption_cases": len(assumption_cases),
        "protected_gate_violations": len(gate_violations),
        "hidden_fact_exact_leaks": len(hidden_leaks),
        "high_urgency_waits": len(high_waits),
        "note": "Automatic checks measure hard constraint failures only. Quality uplift must be decided from blind_review.json before opening blind_key.json.",
    }

    (OUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "blind_review.json").write_text(json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "blind_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
