#!/usr/bin/env bash
# Baut das Lambda-Deployment-Paket (lambda.zip) fuer den pacs.008-Generator.
# Aufruf:  ./aws/build_lambda.sh        (aus dem pacs008-generator-Ordner)
# Ergebnis: aws/lambda.zip  -> in AWS Lambda hochladen (oder via S3)
set -euo pipefail
cd "$(dirname "$0")/.."

BUILD=aws/build
ZIP=aws/lambda.zip
rm -rf "$BUILD" "$ZIP"
mkdir -p "$BUILD"

echo ">> Dependencies (Linux-Wheels fuer Lambda-Runtime) ..."
pip3 install --quiet --target "$BUILD" \
    --platform manylinux2014_x86_64 --implementation cp \
    --python-version 3.12 --only-binary=:all: \
    "xmlschema>=3.0" "PyYAML>=6.0"

echo ">> Code + Schemas + Katalog ..."
cp -R pacs008_generator "$BUILD/"
cp -R schemas "$BUILD/"
cp error_catalog.yaml "$BUILD/"
cp aws/lambda_handler.py "$BUILD/"

# validator.py sucht schemas/ relativ zum Paket-Parent -> liegt im Zip-Root, passt.
find "$BUILD" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo ">> Zip ..."
(cd "$BUILD" && zip -qr "../lambda.zip" .)
rm -rf "$BUILD"
echo "Fertig: $ZIP ($(du -h "$ZIP" | cut -f1))"
echo ""
echo "AWS-Konfiguration:"
echo "  Runtime:  Python 3.12 (x86_64)"
echo "  Handler:  lambda_handler.lambda_handler"
echo "  Memory:   512 MB | Timeout: 60 s"
echo "  Optional: Env OUTPUT_BUCKET=<s3-bucket> fuer XML-Ablage in S3"
