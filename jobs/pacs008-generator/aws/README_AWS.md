# Deployment as AWS Lambda

## Build the package

```bash
cd pacs008-generator
chmod +x aws/build_lambda.sh
./aws/build_lambda.sh          # produces aws/lambda.zip (~2-3 MB)
```

## Create the Lambda (console or CLI)

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

## Invocation

Direct (test event or CLI):

```json
{"count": 20, "error_rate": 0.3, "seed": 42, "error_codes": null}
```

With S3 output (recommended for large batches — Lambda response limit is 6 MB):

```json
{"count": 100, "faulty": 30, "s3_bucket": "my-bucket", "s3_prefix": "pacs008-runs/"}
```

→ XMLs + `manifest.json` end up under `s3://my-bucket/pacs008-runs/<run_id>/`,
the response contains `s3_location` + manifest without XML.
Alternatively set the env vars `OUTPUT_BUCKET` / `OUTPUT_PREFIX`.

Function URL / API Gateway: same JSON body as POST — the handler detects
`event.body` automatically. The demo UI (ui/index.html) can run against the
Lambda with a minimal change (fetch URL).

## IAM

Base: `AWSLambdaBasicExecutionRole` (logs). For S3 additionally `s3:PutObject`
on the target bucket/prefix.

## Notes

- No network access at runtime except optional S3 — no VPC required
- Cold start ~1-2 s (xmlschema parses the XSDs on first call, cached afterwards)
- `schemas/` (MyStandards licence) stays inside the private deployment package
- Local smoke test without AWS: `python3 aws/local_invoke.py`
