"""One-shot: create the `photos` index with the keyword mapping.

Load env vars first:
  export $(cat .env | xargs)   # bash/Git Bash
  # or on PowerShell: Get-Content .env | ForEach-Object { $k,$v=$_.Split('=',2); [System.Environment]::SetEnvironmentVariable($k,$v) }
"""
import json
import os
import sys
from pathlib import Path

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

ENDPOINT = os.environ["ES_ENDPOINT"]
INDEX = os.environ.get("ES_INDEX", "photos")
REGION = os.environ.get("AWS_REGION", "us-east-1")

mapping = json.loads(Path(__file__).with_name("photos-index-mapping.json").read_text())

c = boto3.Session().get_credentials()
auth = AWS4Auth(c.access_key, c.secret_key, REGION, "es", session_token=c.token)
es = OpenSearch(
    hosts=[{"host": ENDPOINT, "port": 443}],
    http_auth=auth, use_ssl=True, verify_certs=True,
    connection_class=RequestsHttpConnection,
)

if es.indices.exists(index=INDEX):
    print(f"{INDEX} already exists")
    sys.exit(0)

resp = es.indices.create(index=INDEX, body=mapping)
print(json.dumps(resp, indent=2))
