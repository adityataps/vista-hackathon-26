resource "aws_s3_bucket" "mockdata" {
  bucket        = "${var.app_name}-mockdata-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "mockdata" {
  bucket = aws_s3_bucket.mockdata.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
