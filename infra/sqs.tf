resource "aws_sqs_queue" "payment_ingest" {
  name                       = "${var.app_name}-payment-ingest"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 86400
}

data "aws_iam_policy_document" "payment_ingest_sqs" {
  statement {
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    resources = [aws_sqs_queue.payment_ingest.arn]
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.mockdata.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "payment_ingest" {
  queue_url = aws_sqs_queue.payment_ingest.id
  policy    = data.aws_iam_policy_document.payment_ingest_sqs.json
}

resource "aws_s3_bucket_notification" "payments" {
  bucket     = aws_s3_bucket.mockdata.id
  depends_on = [aws_sqs_queue_policy.payment_ingest]

  queue {
    queue_arn     = aws_sqs_queue.payment_ingest.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "payments/"
  }
}
