import json
import os
import uuid

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION = os.environ.get("AWS_REGION", "us-east-1")
ES_ENDPOINT = os.environ["ES_ENDPOINT"]
ES_INDEX = os.environ.get("ES_INDEX", "photos")
LEX_BOT_ID = os.environ["LEX_BOT_ID"]
LEX_BOT_ALIAS_ID = os.environ["LEX_BOT_ALIAS_ID"]
LEX_LOCALE_ID = os.environ.get("LEX_LOCALE_ID", "en_US")
URL_TTL = int(os.environ.get("URL_TTL", "3600"))

# words to drop from a fallback keyword search if Lex misses everything
STOPWORDS = {
    "a", "an", "the", "show", "me", "find", "get", "give",
    "photos", "photo", "pictures", "picture", "images", "image",
    "with", "of", "in", "on", "and", "or", "to", "for", "them",
    "please", "some", "any", "is", "are",
}

lex = boto3.client("lexv2-runtime")
s3 = boto3.client("s3")

_creds = boto3.Session().get_credentials()
_auth = AWS4Auth(
    _creds.access_key, _creds.secret_key, REGION, "es",
    session_token=_creds.token,
)
es = OpenSearch(
    hosts=[{"host": ES_ENDPOINT, "port": 443}],
    http_auth=_auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)


def _response(body, status=200):
    return {
        "statusCode": status,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }


def _slot_value(slot):
    if not slot:
        return None
    val = slot.get("value") or {}
    return val.get("interpretedValue") or val.get("originalValue")


def _keywords_from_lex(q):
    resp = lex.recognize_text(
        botId=LEX_BOT_ID,
        botAliasId=LEX_BOT_ALIAS_ID,
        localeId=LEX_LOCALE_ID,
        sessionId=str(uuid.uuid4()),
        text=q,
    )
    intent = (resp.get("sessionState") or {}).get("intent") or {}
    slots = intent.get("slots") or {}
    out = []
    for slot in slots.values():
        v = _slot_value(slot)
        if v:
            out.append(v.strip().lower())
    return out


def _fallback_keywords(q):
    return [w for w in q.lower().split() if w and w not in STOPWORDS]


def _presigned(bucket, key):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=URL_TTL,
    )


def lambda_handler(event, context):
    qs = event.get("queryStringParameters") or {}
    q = (qs.get("q") or "").strip()
    if not q:
        return _response({"results": []})

    keywords = _keywords_from_lex(q) or _fallback_keywords(q)
    if not keywords:
        return _response({"results": []})

    body = {
        "size": 50,
        "query": {"terms": {"labels": keywords}},
    }
    hits = es.search(index=ES_INDEX, body=body).get("hits", {}).get("hits", [])

    results = []
    for hit in hits:
        src = hit.get("_source", {})
        bucket = src.get("bucket")
        key = src.get("objectKey")
        if not bucket or not key:
            continue
        results.append({
            "url": _presigned(bucket, key),
            "labels": src.get("labels", []),
        })
    return _response({"results": results})
