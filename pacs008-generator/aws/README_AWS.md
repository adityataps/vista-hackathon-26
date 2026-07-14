# Deployment als AWS Lambda

## Paket bauen

```bash
cd pacs008-generator
chmod +x aws/build_lambda.sh
./aws/build_lambda.sh          # erzeugt aws/lambda.zip (~2-3 MB)
```

## Lambda anlegen (Konsole oder CLI)

```bash
aws lambda create-function \
  --function-name pacs008-generator \
  --runtime python3.12 --architectures x86_64 \
  --handler lambda_handler.lambda_handler \
  --memory-size 512 --timeout 60 \
  --zip-file fileb://aws/lambda.zip \
  --role arn:aws:iam::<ACCOUNT>:role/<lambda-exec-role>
```

Updates: `aws lambda update-function-code --function-name pacs008-generator --zip-file fileb://aws/lambda.zip`

## Aufruf

Direkt (Test-Event oder CLI):

```json
{"count": 20, "error_rate": 0.3, "seed": 42, "error_codes": null}
```

Mit S3-Ablage (empfohlen fuer grosse Batches — Lambda-Response-Limit ist 6 MB):

```json
{"count": 100, "faulty": 30, "s3_bucket": "mein-bucket", "s3_prefix": "pacs008-runs/"}
```

→ XMLs + `manifest.json` landen unter `s3://mein-bucket/pacs008-runs/<run_id>/`,
Response enthaelt `s3_location` + Manifest ohne XML.
Alternativ Env-Vars `OUTPUT_BUCKET` / `OUTPUT_PREFIX` setzen.

Function URL / API Gateway: gleicher JSON-Body als POST — der Handler erkennt
`event.body` automatisch. Damit kann das Demo-UI (ui/index.html) mit minimaler
Anpassung (fetch-URL) gegen die Lambda laufen.

## IAM

Basis: `AWSLambdaBasicExecutionRole` (Logs). Fuer S3 zusaetzlich `s3:PutObject`
auf den Ziel-Bucket/Prefix.

## Hinweise

- Keine Netzwerkzugriffe zur Laufzeit ausser optional S3 — kein VPC noetig
- Kaltstart ~1-2 s (xmlschema parst die XSDs beim ersten Aufruf, danach gecacht)
- `schemas/` (MyStandards-Lizenz) bleibt im privaten Deployment-Paket — ok fuer internen Gebrauch
- Lokaler Smoke-Test ohne AWS: `python3 aws/local_invoke.py`
