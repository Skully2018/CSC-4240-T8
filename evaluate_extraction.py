"""Run labeled extraction cases against Gemini; never simulates AI."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from diet_rules import key
from preference_agent import parse_preferences, AIError
from config import ConfigError, load_config


def canonical(people):
    return sorted((p['name'].strip().casefold(),p['diet'],
                   tuple(sorted((key(x['ingredient']),x['strength']) for x in p['preferences'])),
                   tuple(sorted(key(x) for x in p['avoid'])),
                   tuple(sorted(key(x) for x in p['allergies']))) for p in people)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--output',default='evaluation/results.json')
    parser.add_argument('--interval',type=float,default=7.0,help='Seconds between calls; increase to fit your project quota')
    args=parser.parse_args()
    if not 1 <= args.limit <= 20:parser.error('--limit must be between 1 and 20')
    if not 0 <= args.interval <= 300:parser.error('--interval must be between 0 and 300 seconds')
    try:
        config = load_config()
    except ConfigError as exc:
        parser.error(str(exc))
    if not config.api_key:
        parser.error('Set GEMINI_API_KEY in .env before running a live evaluation.')
    cases=json.loads((Path(__file__).parent/'evaluation/cases.json').read_text())[:args.limit]
    rows=[]
    for index, case in enumerate(cases):
        if index:
            time.sleep(args.interval)
        start=time.perf_counter()
        row={'id':case['id'],'text':case['text'],'expected':case['expected']}
        try:
            result=parse_preferences({'text':case['text']}, config=config)
            expected=case['expected']
            checks={'clarification':bool(result['questions'])==expected['clarification'],
                    'unsupported':bool(result['unsupported_requests'])==expected['unsupported']}
            if expected['roommates'] is not None:
                checks['profiles']=canonical(result['roommates'])==canonical(expected['roommates'])
            row.update(actual=result,checks=checks,passed=all(checks.values()))
        except (AIError,ValueError) as exc:
            row.update(error=str(exc),passed=False)
        row['seconds']=round(time.perf_counter()-start,3);rows.append(row)
        print(case['id'], 'PASS' if row['passed'] else 'FAIL', row['seconds'],'seconds',flush=True)
        if row.get('error'):
            print('Stopping on runtime error. Resolve the Gemini setup or quota issue before retrying.',flush=True)
            break
    report={'provider':'gemini_api','model':config.model,'interval_seconds':args.interval,'time_utc':datetime.now(timezone.utc).isoformat(),
            'attempted':len(rows),'requested':len(cases),'passed':sum(r['passed'] for r in rows),
            'runtime_errors':sum('error' in r for r in rows),'cases':rows,
            'note':'Exact profile matching applies only to unambiguous cases. Human review of ambiguous cases is still required. This is a small development set, not independent test evidence.'}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Saved',out)


if __name__=='__main__':main()
