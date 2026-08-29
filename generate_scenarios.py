#!/usr/bin/env python3
import json
from pathlib import Path

ARCHETYPES = [
    {
        "role":"frontier_warden",
        "personality":["dutiful","cautious","protective"],
        "goal":"Keep a difficult frontier route safe without causing needless panic.",
        "resources":["6 patrols","trusted scouts","local messengers"],
        "known":["A damaged pass has become less predictable.","Two patrols reported unusual tracks.","The nearest settlement depends on this route."],
        "hidden":["The tracks belong to a creature unknown to this region."],
        "baseline":"Increase patrol attention, verify the tracks, and keep the route open unless evidence justifies closure."
    },
    {
        "role":"coastal_hunter",
        "personality":["independent","curious","practical"],
        "goal":"Understand unusual coastal creature movement before people get hurt.",
        "resources":["small boat","hunting gear","contacts among crews"],
        "known":["Several crews report animals ranging outside normal waters.","No attack has been confirmed.","Weather has been unstable."],
        "hidden":["A larger predator has moved into deeper water."],
        "baseline":"Compare reports from multiple crews and personally inspect the safest edge of the affected waters."
    },
    {
        "role":"regional_ruler",
        "personality":["pragmatic","patient","politically-aware"],
        "goal":"Preserve prosperity and stability while avoiding an unnecessary conflict.",
        "resources":["official messengers","guards","treasury authority","trade envoys"],
        "known":["A neighboring region raised duties on an important route.","Merchants are complaining.","No treaty has been broken."],
        "hidden":["One merchant guild is exaggerating losses to gain leverage."],
        "baseline":"Open negotiations while quietly checking independent trade reports before retaliating."
    },
    {
        "role":"craft_master",
        "personality":["methodical","proud","loyal"],
        "goal":"Protect access to rare materials and understand a newly exposed underground site.",
        "resources":["workshop","apprentices","guild contacts","survey tools"],
        "known":["Workers uncovered worked stone behind an old collapse.","The structure is not in current records.","No one is missing."],
        "hidden":["The chamber predates the current settlement."],
        "baseline":"Secure the entrance and personally inspect samples before authorizing deeper work."
    },
    {
        "role":"young_mage",
        "personality":["analytical","idealistic","inquisitive"],
        "goal":"Understand a subtle magical irregularity without endangering others.",
        "resources":["notes","basic instruments","access to local archives"],
        "known":["Several harmless magical effects behaved inconsistently.","The pattern is recent.","No injuries have occurred."],
        "hidden":["The irregularity is linked to an old magical site outside the region."],
        "baseline":"Compare recent incidents with archive records and look for a shared local cause."
    },
    {
        "role":"former_soldier_companion",
        "personality":["direct","loyal","skeptical"],
        "goal":"Protect close allies while making independent judgments about old military teachings.",
        "resources":["personal gear","old contacts","field experience"],
        "known":["Current reports contradict part of what the old order taught.","A former comrade is nearby.","The contradiction is not yet proof of deception."],
        "hidden":["The old order itself no longer knows the full truth."],
        "baseline":"Speak with trusted former comrades and compare firsthand accounts before confronting the institution."
    },
    {
        "role":"village_head",
        "personality":["community-minded","frugal","decisive"],
        "goal":"Keep a small settlement supplied through a difficult season.",
        "resources":["local labor","grain reserve","cart owners"],
        "known":["A bridge is damaged.","Food stocks are adequate for now.","A longer alternative road remains open."],
        "hidden":["The bridge can be repaired faster than expected if a nearby quarry helps."],
        "baseline":"Ration transport capacity, send essential goods by the longer road, and inspect repair needs immediately."
    },
    {
        "role":"merchant_captain",
        "personality":["opportunistic","experienced","risk-aware"],
        "goal":"Complete profitable trade without gambling the lives of the crew.",
        "resources":["cargo ship","crew","cash reserve","port contacts"],
        "known":["Piracy rumors increased on the direct route.","No trusted witness has confirmed an attack.","A slower route is available."],
        "hidden":["The rumors were seeded by a rival trader."],
        "baseline":"Delay departure briefly to verify reports while preparing the slower route as a fallback."
    },
    {
        "role":"forest_keeper",
        "personality":["observant","reserved","protective"],
        "goal":"Preserve a forest region while preventing conflict with nearby settlements.",
        "resources":["rangers","animal knowledge","local guides"],
        "known":["Large animals are leaving their usual territory.","Logging increased near one boundary.","No disease has been observed."],
        "hidden":["A territorial predator shifted its hunting range."],
        "baseline":"Reduce pressure near the disturbed boundary and track the movement pattern before blaming the settlements."
    },
    {
        "role":"local_healer",
        "personality":["compassionate","practical","calm"],
        "goal":"Protect a community during an unfamiliar but limited illness.",
        "resources":["herbs","assistants","community trust"],
        "known":["Five people share similar symptoms.","All drank from the same roadside well.","None are critically ill."],
        "hidden":["A harmless seasonal algae bloom caused the symptoms."],
        "baseline":"Stop use of the well temporarily, treat symptoms, and compare the affected group for other shared exposures."
    }
]

TWISTS = [
    ("low_urgency", 3, "The situation has been stable for two days.", ["Do not invent a crisis."]),
    ("rising_urgency", 7, "A second independent report confirms that the problem is spreading.", ["Act proportionally to new evidence."]),
    ("resource_shortage", 6, "One important resource is temporarily unavailable.", ["Do not assume new resources appear."]),
    ("conflicting_report", 5, "A trusted source and a casual witness disagree.", ["Treat information certainty explicitly."]),
    ("ally_request", 6, "A respected ally asks for immediate help with a related problem.", ["Balance own goal against relationship obligations."]),
    ("public_pressure", 6, "Local people are demanding visible action.", ["Do not confuse popularity with truth."]),
    ("new_route", 5, "A safe but slower alternative route becomes available.", ["Travel must follow reachable routes."]),
    ("minor_loss", 6, "A recent attempt cost time and supplies but caused no casualties.", ["Failure may change the plan; do not reset to the same action blindly."]),
    ("fresh_information", 7, "A messenger brings a credible new fact relevant to the goal.", ["Use only information explicitly listed as known."]),
    ("protected_story_gate", 8, "A larger unresolved matter cannot be concluded without a specific absent person, but ordinary surrounding actions may continue.", ["Do not resolve the protected matter offscreen.","Do not freeze all activity."])
]

def main():
    scenarios = []
    sid = 1
    for actor in ARCHETYPES:
        for twist, urgency, change, extra_constraints in TWISTS:
            scenarios.append({
                "id": f"S{sid:03d}",
                "role": actor["role"],
                "personality": actor["personality"],
                "goal": actor["goal"],
                "urgency": urgency,
                "location": "current_region",
                "reachable_locations": ["current_region","nearby_settlement","known_route_stop"],
                "resources": actor["resources"],
                "known_facts": actor["known"] + [change],
                "relationships": {"trusted_ally":"positive","local_authority":"neutral"},
                "constraints": [
                    "Do not use knowledge not listed in known_facts.",
                    "Do not teleport or assume unreachable travel.",
                    "Do not create money, troops, equipment, or authority not listed in resources.",
                    "Prefer a concrete action over passive waiting when action is causally justified.",
                    "Protected matters may be prepared for but not irreversibly resolved without required participation."
                ] + extra_constraints,
                "evaluation_hidden_facts": actor["hidden"],
                "deterministic_baseline": actor["baseline"],
                "twist": twist
            })
            sid += 1

    assert len(scenarios) == 100
    Path("scenarios.json").write_text(json.dumps(scenarios, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote 100 anonymized scenarios to scenarios.json")

if __name__ == "__main__":
    main()
