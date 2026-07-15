# ── S3 VPC gateway endpoint (free) so Lambda in VPC can reach S3 ──────────────
data "aws_route_tables" "default" {
  vpc_id = data.aws_vpc.default.id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = data.aws_vpc.default.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.default.ids
}

# ── Lambda execution role ─────────────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_ingest" {
  name               = "${var.app_name}-lambda-ingest"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda_ingest.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_ingest" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.mockdata.arn}/payments/*"]
  }
  statement {
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [aws_sqs_queue.payment_ingest.arn]
  }
}

resource "aws_iam_role_policy" "lambda_ingest" {
  name   = "${var.app_name}-lambda-ingest"
  role   = aws_iam_role.lambda_ingest.id
  policy = data.aws_iam_policy_document.lambda_ingest.json
}

resource "aws_cloudwatch_log_group" "lambda_ingest" {
  name              = "/aws/lambda/${var.app_name}-payment-xml-ingest"
  retention_in_days = 7
}

# ── Lambda function ────────────────────────────────────────────────────────────
# image_uri uses the base Lambda image as a placeholder for the initial apply;
# CI pushes the real image and calls update-function-code after each push.
resource "aws_lambda_function" "payment_ingest" {
  function_name = "${var.app_name}-payment-xml-ingest"
  role          = aws_iam_role.lambda_ingest.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.ingest.repository_url}:latest"
  timeout       = 60
  memory_size   = 512

  image_config {
    command = ["handler.lambda_handler"]
  }

  vpc_config {
    subnet_ids         = data.aws_subnets.public.ids
    security_group_ids = [aws_security_group.lambda_ingest.id]
  }

  environment {
    variables = {
      DATABASE_URL = "postgresql://${local.db_user}:${random_password.db.result}@${aws_db_instance.main.endpoint}/${local.db_name}"
      BACKEND_URL  = var.backend_url
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_cloudwatch_log_group.lambda_ingest,
    aws_vpc_endpoint.s3,
  ]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# ── SQS → Lambda trigger ───────────────────────────────────────────────────────
resource "aws_lambda_event_source_mapping" "payment_ingest" {
  event_source_arn = aws_sqs_queue.payment_ingest.arn
  function_name    = aws_lambda_function.payment_ingest.arn
  batch_size       = 10
  enabled          = true
}
