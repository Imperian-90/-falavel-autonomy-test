#!/usr/bin/env python3
import json, os, random, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API_KEY = os.environ.get('GEMINI_API_KEY','').strip()
MODEL = os.environ.get('GEMINI_MODEL','gemini-3.6-flash').strip() or 'gemini-3.6-flash'
DELAY = float(os.environ.get('GEMINI_DELAY_SECONDS','13.2'))
SCENARIO_FILE = Path('scenarios.json')
OUT = Path('results_v2'); OUT.mkdir(exist_ok=True)
if not API_KEY:
    sys.exit('GEMINI_API_KEY missing')

SYSTEM = '''You choose exactly one next autonomous action for a fantasy-world actor.
Use ONLY supplied known facts, resources, relationships, reachable locations and constraints.
Never invent hidden facts, authority, money, contacts, routes, magic or resources. Never teleport.
A protected story matter may be investigated or prepared for, but not irreversibly resolved.
Choose a concrete action that fits personality and goal. Waiting is allowed only if rational.
Keep every text field concise. Return JSON only.'''

SCHEMA = {
 'type':'object','properties':{
  'intent':{'type':'string'},
  'expected_effect':{'type':'string'},
  'knowledge_indices':{'type':'array','items':{'type':'integer'}},
  'resource_indices':{'type':'array','items':{'type':'integer'}},
  'new_assumptions':{'type':'array','items':{'type':'string'}},
  'protected_matter_action':{'type':'string','enum':['none','prepare','resolve']},
  'waits':{'type':'boolean'}
 },
 'required':['intent','expected_effect','knowledge_indices','resource_indices','new_assumptions','protected_matter_action','waits'],
 'additionalProperties':False
}

def prompt(s):
    known='\n'.join(f'{i+1}. {x}' for i,x in enumerate(s['known_facts']))
    res='\n'.join(f'{i+1}. {x}' for i,x in enumerate(s['resources']))
    con='\n'.join(f'- {x}' for x in s['constraints'])
    return f'''Role: {s['role']}\nPersonality: {', '.join(s['personality'])}\nGoal: {s['goal']}\nUrgency: {s['urgency']}/10\nLocation: {s['location']}\nReachable: {', '.join(s['reachable_locations'])}\nRelationships: {json.dumps(s['relationships'],ensure_ascii=False)}\nKnown facts:\n{known}\nResources:\n{res}\nConstraints:\n{con}\nChoose the single best next autonomous action. Intent and expected_effect each max 30 words.'''

def call(s):
    url='https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(MODEL,safe='')+':generateContent?key='+urllib.parse.quote(API_KEY,safe='')
    body={'system_instruction':{'parts':[{'text':SYSTEM}]},'contents':[{'role':'user','parts':[{'text':prompt(s)}]}], 'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':SCHEMA,'maxOutputTokens':1200}}
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            raw=json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg=e.read().decode('utf-8','replace')
        raise RuntimeError(f'HTTP {e.code}: {msg[:1600]}')
    txt=''.join(p.get('text','') for p in raw['candidates'][0]['content']['parts']).strip()
    return json.loads(txt), raw.get('modelVersion'), raw.get('usageMetadata',{})

def validate(s,d):
    problems=[]
    if any(not isinstance(i,int) or i<1 or i>len(s['known_facts']) for i in d.get('knowledge_indices',[])): problems.append('knowledge_index')
    if any(not isinstance(i,int) or i<1 or i>len(s['resources']) for i in d.get('resource_indices',[])): problems.append('resource_index')
    if d.get('new_assumptions'): problems.append('unsupported_assumption')
    if s.get('twist')=='protected_story_gate' and d.get('protected_matter_action')=='resolve': problems.append('protected_gate')
    blob=json.dumps(d,ensure_ascii=False).lower()
    for h in s.get('evaluation_hidden_facts',[]):
        if len(h.strip())>=20 and h.lower().strip() in blob: problems.append('hidden_leak')
    return problems

def main():
    scenarios=json.loads(SCENARIO_FILE.read_text(encoding='utf-8'))
    rows=[]; blind=[]; key=[]
    rng=random.Random(20260829)
    for n,s in enumerate(scenarios,1):
        print(f'[{n}/{len(scenarios)}] {s["id"]}',flush=True)
        try:
            d,ver,usage=call(s); probs=validate(s,d)
            rows.append({'scenario_id':s['id'],'role':s['role'],'twist':s['twist'],'baseline':s['deterministic_baseline'],'gemini':d,'problems':probs,'model_version':ver,'usage':usage})
            baseline={'intent':s['deterministic_baseline']}
            agent={'intent':d['intent']}
            if rng.random()<.5:
                blind.append({'scenario_id':s['id'],'role':s['role'],'personality':s['personality'],'goal':s['goal'],'urgency':s['urgency'],'known_facts':s['known_facts'],'resources':s['resources'],'constraints':s['constraints'],'A':baseline,'B':agent})
                key.append({'scenario_id':s['id'],'A':'baseline','B':'gemini'})
            else:
                blind.append({'scenario_id':s['id'],'role':s['role'],'personality':s['personality'],'goal':s['goal'],'urgency':s['urgency'],'known_facts':s['known_facts'],'resources':s['resources'],'constraints':s['constraints'],'A':agent,'B':baseline})
                key.append({'scenario_id':s['id'],'A':'gemini','B':'baseline'})
        except Exception as e:
            rows.append({'scenario_id':s['id'],'role':s['role'],'twist':s['twist'],'baseline':s['deterministic_baseline'],'error':str(e)})
        if n<len(scenarios): time.sleep(DELAY)
    ok=[r for r in rows if 'gemini' in r]
    summary={'model':MODEL,'requested':len(scenarios),'completed':len(ok),'errors':len(rows)-len(ok),'hard_valid':sum(not r['problems'] for r in ok),'with_assumptions':sum('unsupported_assumption' in r['problems'] for r in ok),'protected_gate_violations':sum('protected_gate' in r['problems'] for r in ok),'hidden_leaks':sum('hidden_leak' in r['problems'] for r in ok)}
    for name,obj in [('results.json',rows),('blind_review.json',blind),('blind_key.json',key),('summary.json',summary)]:
        (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
