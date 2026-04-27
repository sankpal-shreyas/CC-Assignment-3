import os
import urllib.parse
from datetime import datetime, timezone

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION = os.environ.get("AWS_REGION", "us-east-1")
ES_ENDPOINT = os.environ["ES_ENDPOINT"]
ES_INDEX = os.environ.get("ES_INDEX", "photos")

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")

_creds = boto3.Session().get_credentials()
_auth = AWS4Auth(
    _creds.access_key,
    _creds.secret_key,
    REGION,
    "es",
    session_token=_creds.token,
)

es = OpenSearch(
    hosts=[{"host": ES_ENDPOINT, "port": 443}],
    http_auth=_auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)


def _custom_labels(metadata):
    # boto3 lower-cases x-amz-meta-* keys, so the header
    # x-amz-meta-customLabels shows up here as "customlabels"
    raw = metadata.get("customlabels", "") if metadata else ""
    return [s.strip() for s in raw.split(",") if s.strip()]


def lambda_handler(event, context):
    indexed = 0
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        rek = rekognition.detect_labels(
            Image={"S3Object": {"Bucket": bucket, "Name": key}},
            MaxLabels=20,
            MinConfidence=80,
        )
        labels = [l["Name"].lower() for l in rek.get("Labels", [])]

        head = s3.head_object(Bucket=bucket, Key=key)
        labels.extend(l.lower() for l in _custom_labels(head.get("Metadata")))

        # de-dupe while keeping order
        seen = set()
        labels = [l for l in labels if not (l in seen or seen.add(l))]

        doc = {
            "objectKey": key,
            "bucket": bucket,
            "createdTimestamp": datetime.now(timezone.utc).isoformat(),
            "labels": labels,
        }
        es.index(index=ES_INDEX, id=key, body=doc)
        print(f"indexed {bucket}/{key} with labels: {labels}")
        indexed += 1

    return {"statusCode": 200, "indexed": indexed}
