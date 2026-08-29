#!/usr/bin/env python3
import json, os, random, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API_KEY=os.environ.get('GEMINI_API_KEY','').strip()
MODEL=os.environ.get('GEMINI_MODEL','gemini-3.6-flash').strip()
DELAY=float(os.environ.get('GEMINI_DELAY_SECONDS','10'))
SCENARIO_FILE=Path(os.environ.get('SCENARIO_FILE','scenarios.json'))
OUT=Path(os.environ.get('OUT_DIR','results_multi')); OUT.mkdir(parents=True,exist_ok=True)
MAX_RETRIES=5
if not API_KEY: sys.exit('GEMINI_API_KEY missing')

SYSTEM='''You generate exactly three genuinely different autonomous strategies for one fantasy-world actor.\nYou are not the GM. Never invent facts, resources, authority, routes or secret knowledge.\nAll strategies must respect the actor's known facts, personality, goal, location, reachable locations, resources and protected story gates.\nThe three strategies must differ in method, not just wording. Return only JSON.'''

SCHEMA={
 'type':'object','properties':{
  'strategies':{'type':'array','minItems':3,'maxItems':3,'items':{
   'type':'object','properties':{
    'intent':{'type':'string'},
    'steps':{'type':'array','minItems':1,'maxItems':3,'items':{'type':'string'}},
    'approach':{'type':'string','enum':['investigate','protect','negotiate','prepare','travel','delegate','observe','contain','repair','trade']},
    'knowledge_indices':{'type':'array','items':{'type':'integer'}},
    'resource_indices':{'type':'array','items':{'type':'integer'}},
    'new_assumptions':{'type':'array','items':{'type':'string'}},
    'destination':{'type':'string'},
    'risk_level':{'type':'string','enum':['low','moderate','high']},
    'commitment':{'type':'string','enum':['reversible','moderate','irreversible']},
    'waits':{'type':'boolean'},
    'protected_matter_action':{'type':'string','enum':['none','prepare','resolve']},
    'expected_world_effect':{'type':'string'}
   },
   'required':['intent','steps','approach','knowledge_indices','resource_indices','new_assumptions','destination','risk_level','commitment','waits','protected_matter_action','expected_world_effect'],
   'additionalProperties':False
  }}
 },'required':['strategies'],'additionalProperties':False
}

def prompt(s):
    known='\n'.join(f'{i+1}. {x}' for i,x in enumerate(s['known_facts']))
    resources='\n'.join(f'{i+1}. {x}' for i,x in enumerate(s['resources']))
    constraints='\n'.join('- '+x for x in s['constraints'])
    return f'''SCENARIO {s['id']}\nRole: {s['role']}\nPersonality: {', '.join(s['personality'])}\nGoal: {s['goal']}\nUrgency: {s['urgency']}/10\nLocation: {s['location']}\nReachable: {', '.join(s['reachable_locations'])}\nRelationships: {json.dumps(s['relationships'])}\n\nKnown facts:\n{known}\n\nResources:\n{resources}\n\nConstraints:\n{constraints}\n\nGenerate exactly three materially different feasible strategies. destination must be 'none' if no travel is proposed, otherwise one exact item from Reachable. Never list an assumption merely to make an impossible strategy possible.'''

def call(s):
    url='https://generativelanguage.googleapis.com/v1beta/models/'+urllib.parse.quote(MODEL,safe='')+':generateContent?key='+urllib.parse.quote(API_KEY,safe='')
    body={'system_instruction':{'parts':[{'text':SYSTEM}]},'contents':[{'role':'user','parts':[{'text':prompt(s)}]}], 'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':SCHEMA,'maxOutputTokens':1800}}
    data=json.dumps(body).encode()
    last=None
    for n in range(MAX_RETRIES+1):
        req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=90) as r: raw=json.loads(r.read().decode())
            text=''.join(p.get('text','') for p in raw['candidates'][0]['content']['parts']).strip()
            return json.loads(text), raw.get('modelVersion'), raw.get('usageMetadata',{})
        except urllib.error.HTTPError as e:
            payload=e.read().decode('utf-8','replace'); last=f'HTTP {e.code}: {payload[:500]}'
            if e.code not in (429,500,502,503,504) or n==MAX_RETRIES: raise RuntimeError(last)
            time.sleep(min(60,4*(2**n)+random.random()))
        except Exception as e:
            last=repr(e)
            if n==MAX_RETRIES: raise
            time.sleep(min(45,3*(2**n)+random.random()))
    raise RuntimeError(last or 'unknown')

def validate(s,d):
    probs=[]
    for i in d.get('knowledge_indices',[]):
        if not isinstance(i,int) or not 1<=i<=len(s['known_facts']): probs.append('bad_knowledge_index')
    for i in d.get('resource_indices',[]):
        if not isinstance(i,int) or not 1<=i<=len(s['resources']): probs.append('bad_resource_index')
    if d.get('new_assumptions'): probs.append('unsupported_assumption')
    dest=d.get('destination','none')
    if dest!='none' and dest not in s['reachable_locations']: probs.append('unreachable_destination')
    if s['twist']=='protected_story_gate' and d.get('protected_matter_action')=='resolve': probs.append('protected_gate_violation')
    if s['urgency']>=7 and d.get('waits'): probs.append('high_urgency_wait')
    blob=json.dumps(d,ensure_ascii=False).lower()
    for hidden in s.get('evaluation_hidden_facts',[]):
        if len(hidden)>=20 and hidden.lower() in blob: probs.append('hidden_fact_leak')
    hard={'bad_knowledge_index','bad_resource_index','unsupported_assumption','unreachable_destination','protected_gate_violation','hidden_fact_leak'}
    return {'valid':not any(x in hard for x in probs),'problems':probs}

def engine_score(s,d,v):
    if not v['valid']: return -10000
    score=100.0
    score+=min(12,len(set(d.get('knowledge_indices',[])))*3)
    score+=min(6,len(set(d.get('resource_indices',[])))*2)
    if s['urgency']>=7: score += 8 if not d.get('waits') else -18
    elif s['urgency']<=3: score += 4 if d.get('commitment')=='reversible' else -3
    if s['twist']=='protected_story_gate':
        score += 10 if d.get('protected_matter_action')=='prepare' else 3 if d.get('protected_matter_action')=='none' else -100
    if s['twist'] in ('conflicting_report','low_urgency') and d.get('commitment')=='reversible': score+=6
    if s['twist']=='rising_urgency' and d.get('approach') in ('protect','contain','investigate','prepare'): score+=5
    if s['twist']=='fresh_information' and len(set(d.get('knowledge_indices',[])))>=2: score+=5
    if s['twist']=='public_pressure' and d.get('approach')=='investigate': score+=3
    if s['twist']=='resource_shortage' and len(set(d.get('resource_indices',[])))>=1: score+=3
    if d.get('commitment')=='irreversible' and s['urgency']<8: score-=7
    return score

def main():
    scenarios=json.loads(SCENARIO_FILE.read_text())
    rows=[]; blind=[]; key=[]; rng=random.Random(20260829)
    for n,s in enumerate(scenarios,1):
        print(f'[{n}/{len(scenarios)}] {s["id"]}',flush=True)
        try:
            obj,ver,usage=call(s)
            ss=obj.get('strategies',[])
            vals=[validate(s,d) for d in ss]
            scores=[engine_score(s,d,v) for d,v in zip(ss,vals)]
            best=max(range(len(ss)),key=lambda i:scores[i])
            chosen=ss[best]
            pair=[{'intent':s['deterministic_baseline']},{'intent':chosen['intent']}]
            rng.shuffle(pair)
            a_is_baseline=pair[0]['intent']==s['deterministic_baseline']
            blind.append({'scenario_id':s['id'],'role':s['role'],'twist':s['twist'],'urgency':s['urgency'],'personality':s['personality'],'goal':s['goal'],'known_facts':s['known_facts'],'resources':s['resources'],'constraints':s['constraints'],'A':pair[0],'B':pair[1]})
            key.append({'scenario_id':s['id'],'A':'baseline' if a_is_baseline else 'hybrid','B':'hybrid' if a_is_baseline else 'baseline'})
            rows.append({'scenario_id':s['id'],'baseline':s['deterministic_baseline'],'strategies':ss,'validation':vals,'engine_scores':scores,'chosen_index':best,'chosen':chosen,'model_version':ver,'usage':usage})
        except Exception as e:
            rows.append({'scenario_id':s['id'],'baseline':s['deterministic_baseline'],'error':str(e)})
        if n<len(scenarios): time.sleep(DELAY)
    ok=[r for r in rows if 'chosen' in r]
    summ={'model':MODEL,'requested':len(scenarios),'completed':len(ok),'errors':len(rows)-len(ok),'all_three_valid':sum(all(v['valid'] for v in r['validation']) for r in ok),'at_least_one_valid':sum(any(v['valid'] for v in r['validation']) for r in ok),'selected_invalid':sum(not r['validation'][r['chosen_index']]['valid'] for r in ok),'protected_gate_violations_total':sum(sum('protected_gate_violation' in v['problems'] for v in r['validation']) for r in ok),'unsupported_assumptions_total':sum(sum('unsupported_assumption' in v['problems'] for v in r['validation']) for r in ok)}
    for name,data in [('results.json',rows),('blind_review.json',blind),('blind_key.json',key),('summary.json',summ)]: (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(json.dumps(summ,indent=2))
if __name__=='__main__': main()
