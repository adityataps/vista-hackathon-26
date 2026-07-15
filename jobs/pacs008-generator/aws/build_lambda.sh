#!/usr/bin/env bash
# Builds the Lambda deployment package (lambda.zip) for the pacs.008 generator.
# Usage:  ./aws/build_lambda.sh        (from the pacs008-generator folder)
# Result: aws/lambda.zip  -> upload to AWS Lambda (or via S3)
set -euo pipefail
cd "$(dirname "$0")/.."

BUILD=aws/build
ZIP=aws/lambda.zip
rm -rf "$BUILD" "$ZIP"
mkdir -p "$BUILD"

echo ">> Dependencies (Linux wheels for the Lambda runtime) ..."
pip3 install --quiet --target "$BUILD" \
    --platform manylinux2014_x86_64 --implementation cp \
    --python-version 3.12 --only-binary=:all: \
    "xmlschema>=3.0" "PyYAML>=6.0"

echo ">> Code + schemas + catalog ..."
cp -R pacs008_generator "$BUILD/"
cp -R schemas "$BUILD/"
cp error_catalog.yaml "$BUILD/"
cp aws/lambda_handler.py "$BUILD/"

# validator.py resolves schemas/ relative to the package parent -> zip root, fine.
find "$BUILD" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo ">> Zip ..."
(cd "$BUILD" && zip -qr "../lambda.zip" .)
rm -rf "$BUILD"
echo "Done: $ZIP ($(du -h "$ZIP" | cut -f1))"
echo ""
echo "AWS configuration:"
echo "  Runtime:  Python 3.12 (x86_64)"
echo "  Handler:  lambda_handler.lambda_handler"
echo "  Memory:   512 MB | Timeout: 60 s"
echo "  Optional: env OUTPUT_BUCKET=<s3-bucket> for storing XMLs in S3"
