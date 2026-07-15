# ALB outputs (Task 8)
output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}

# S3 outputs (Task 4)
output "s3_bucket_name" {
  value = aws_s3_bucket.mockdata.bucket
}

# IAM outputs (Task 5)
output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

# ECS outputs (Task 9)
output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecr_ingest_url" {
  value = aws_ecr_repository.ingest.repository_url
}

output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "sqs_payment_ingest_url" {
  value = aws_sqs_queue.payment_ingest.url
}

output "s3_knowledge_base_bucket" {
  value = aws_s3_bucket.knowledge_base.bucket
}

output "knowledge_base_id" {
  value = aws_bedrockagent_knowledge_base.main.id
}

output "guardrail_id" {
  value = aws_bedrock_guardrail.pay_investigator.guardrail_id
}

output "guardrail_arn" {
  value = aws_bedrock_guardrail.pay_investigator.guardrail_arn
}
