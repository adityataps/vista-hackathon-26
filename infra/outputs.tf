output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "ecr_backend_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "s3_bucket_name" {
  value = aws_s3_bucket.mockdata.bucket
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
