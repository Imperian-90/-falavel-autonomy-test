import os
import json
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import psycopg2

raw = os.environ["DATABASE_URL"].strip()
if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
    raw = raw[1:-1]

parts = urlsplit(raw)
query = [
    (k, v)
    for k, v in parse_qsl(parts.query, keep_blank_values=True)
    if k != "channel_binding"
]
dsn = urlunsplit(
    (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
)

conn = psycopg2.connect(dsn)
cur = conn.cursor()

cur.execute(
    "select imperian1.aws_smoke_test_current(%s::uuid,%s,%s,10)",
    (
        os.environ["FALAVEL_CAMPAIGN_ID"],
        os.environ["FALAVEL_CHECKPOINT"],
        os.environ["FALAVEL_BRANCH_ID"],
    ),
)

result = cur.fetchone()[0]
conn.commit()
cur.close()
conn.close()

print("FALAVEL_SMOKE_SUMMARY " + json.dumps(result, sort_keys=True))

if not result.get("passed", False):
    raise SystemExit(2)

print("FALAVEL_10_TURN_SMOKE_PASS")
