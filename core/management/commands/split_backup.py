"""
Utility script (not a management command) — run directly with:
  python core/management/commands/split_backup.py
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

with open('db_backup.json') as f:
    data = json.load(f)

# Models that cause problems on cross-machine restore:
#   sessions.session      — stale login sessions, useless on new machine
#   admin.logentry        — references content_type integer IDs which differ per machine
#   users.useractivitylog — 4932 records, purely audit/reporting, not operational
EXCLUDE_MODELS = {
    'sessions.session',
    'admin.logentry',
    'users.useractivitylog',
}

safe = [r for r in data if r['model'] not in EXCLUDE_MODELS]
excluded = [r for r in data if r['model'] in EXCLUDE_MODELS]

with open('db_backup_portable.json', 'w') as f:
    json.dump(safe, f, indent=2)

from collections import Counter
counts = Counter(r['model'] for r in safe)
print('=== db_backup_portable.json ===')
for model, count in sorted(counts.items()):
    print('  {:<55} {:>5}'.format(model, count))
print('  {:<55} {:>5}'.format('TOTAL', len(safe)))
print()
print('Excluded {} records across {} model types:'.format(len(excluded), len(EXCLUDE_MODELS)))
for m in sorted(EXCLUDE_MODELS):
    n = sum(1 for r in excluded if r['model'] == m)
    print('  {} — {} records'.format(m, n))
print()
print('Portable backup written to: db_backup_portable.json')
