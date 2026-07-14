# AWS Infrastructure Design — PayInvestigator
**Date:** 2026-07-14  
**Region:** `us-west-2`  
**Domain:** `vistahack26.tapshalkar.com` (Cloudflare DNS → AWS ALB)

---

## Architecture Overview

```
GitHub (push to main)
        │
        ▼
GitHub Actions (OIDC → AWS)
  1. Build + push backend image  → ECR (payinvestigator-backend)
  2. Build + push frontend image → ECR (payinvestigator-frontend)
  3. ECS deploy backend service  (rolling update, wait for stability)
  4. ECS deploy frontend service (rolling update, wait for stability)
        │
        ▼
Cloudflare DNS (DNS only, grey cloud)
  vistahack26.tapshalkar.com  CNAME →  ALB DNS name
        │
        ▼
ALB (HTTPS :443, ACM cert)
  HTTP :80 → redirect to HTTPS
  /api/*   → Backend Target Group  (Fargate task, port 8080)
  /*       → Frontend Target Group (Fargate task, port 80)
        │             │
        ▼             ▼
  FastAPI        Nginx serving
  + LangGraph    React build
  (:8080)        (:80)
      │
      ├── S3 (mock data, seeded into SQLite on startup)
      └── Bedrock (claude-sonnet-4-6)
```

**TLS:** ACM cert on the ALB terminates HTTPS. Cloudflare is DNS-only (grey cloud) — client talks directly to ALB, no Cloudflare proxy. No cert needed on the containers.

---

## AWS Resources

| Resource | Name / Details |
|---|---|
| `aws_ecr_repository` x2 | `payinvestigator-backend`, `payinvestigator-frontend`. Lifecycle: keep last 5 images. |
| `aws_ecs_cluster` | `payinvestigator` |
| `aws_ecs_task_definition` (backend) | Fargate, 0.5 vCPU / 1 GB. Container: FastAPI on port 8080. CloudWatch logs. Uses task IAM role for Bedrock + S3. |
| `aws_ecs_task_definition` (frontend) | Fargate, 0.25 vCPU / 0.5 GB. Container: Nginx serving React on port 80. |
| `aws_ecs_service` x2 | One per task def. `desired_count = 1`. Rolling deploy: min 0%, max 200%. |
| `aws_lb` | Internet-facing ALB. Subnets: 2+ public subnets from default VPC. |
| `aws_lb_listener` (HTTP) | Port 80 → redirect to HTTPS 443. |
| `aws_lb_listener` (HTTPS) | Port 443, ACM cert. Default action → frontend TG. |
| `aws_lb_listener_rule` | Path `/api/*` → backend TG. Priority 10. |
| `aws_lb_target_group` (backend) | Port 8080, protocol HTTP. Health check: `GET /health`. |
| `aws_lb_target_group` (frontend) | Port 80, protocol HTTP. Health check: `GET /`. |
| `aws_acm_certificate` | `vistahack26.tapshalkar.com`, DNS validation. |
| `aws_acm_certificate_validation` | Waits for cert to be issued before ALB listener uses it. |
| `aws_security_group` (ALB) | Inbound: 80 + 443 from `0.0.0.0/0`. Outbound: all. |
| `aws_security_group` (backend task) | Inbound: 8080 from ALB SG only. Outbound: all. |
| `aws_security_group` (frontend task) | Inbound: 80 from ALB SG only. Outbound: all. |
| `aws_s3_bucket` | `payinvestigator-mockdata-<account_id>` — private. Mock data JSON files. |
| `aws_iam_role` (task execution) | Shared across both tasks. ECR pull + CloudWatch Logs write. |
| `aws_iam_role` (backend task) | `bedrock:InvokeModel` on `claude-sonnet-4-6`; `s3:GetObject` + `s3:ListBucket` on mock data bucket. |
| `aws_iam_role` (GitHub Actions) | OIDC trust: `repo:adityataps/vista-hackathon-26:ref:refs/heads/main`. ECR push on both repos; ECS `RegisterTaskDefinition` + `UpdateService` + `DescribeServices` + `DescribeTaskDefinition`. |
| `aws_iam_openid_connect_provider` | GitHub Actions (`token.actions.githubusercontent.com`). |
| `aws_cloudwatch_log_group` x2 | `/ecs/payinvestigator-backend`, `/ecs/payinvestigator-frontend`. Retention: 7 days. |
| `cloudflare_record` | CNAME, name `vistahack26`, value = ALB DNS name, proxied = `false`. |
| `cloudflare_record` (ACM validation) | CNAME record created by ACM validation — managed by Terraform. |

---

## Terraform Layout

```
infra/
├── main.tf            # aws + cloudflare provider config; data sources (default VPC, subnets)
├── variables.tf       # region, account_id, cloudflare_zone_id, cloudflare_api_token
├── outputs.tf         # alb_dns_name, ecr_backend_url, ecr_frontend_url, s3_bucket_name
├── ecr.tf             # aws_ecr_repository x2, lifecycle policies
├── ecs.tf             # cluster, task definitions, services
├── alb.tf             # ALB, listeners, target groups, listener rules
├── acm.tf             # certificate + DNS validation record + validation wait
├── security_groups.tf # ALB SG, backend task SG, frontend task SG
├── iam.tf             # task execution role; backend task role; GitHub Actions OIDC role + provider
├── s3.tf              # mock data bucket + block public access
├── cloudwatch.tf      # log groups
└── dns.tf             # cloudflare_record (CNAME to ALB + ACM validation record)
```

State: local `terraform.tfstate` (sufficient for a hackathon, do not commit).  
Sensitive vars in `terraform.tfvars` (gitignored): `cloudflare_api_token`.

---

## GitHub Actions Pipeline

**File:** `.github/workflows/deploy.yml`  
**Trigger:** push to `main`

```yaml
steps:
  1.  actions/checkout
  2.  aws-actions/configure-aws-credentials   # OIDC, no long-lived keys
  3.  aws-actions/amazon-ecr-login
  4.  Build backend image; push :latest + :<git-sha> to ECR
  5.  Build frontend image; push :latest + :<git-sha> to ECR
  6.  aws ecs describe-task-definition        # download current backend task def
  7.  aws-actions/amazon-ecs-render-task-definition  # swap in new backend image
  8.  aws-actions/amazon-ecs-deploy-task-definition  # deploy + wait for stability
  9.  Repeat steps 6–8 for frontend service
```

**GitHub Secrets required:**
- `AWS_ACCOUNT_ID`

No SSH keys. No long-lived AWS credentials. OIDC handles everything.

---

## Docker Images

```dockerfile
# Backend — FastAPI + LangGraph (backend/Dockerfile)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["sh", "-c", "python seed_db.py && uvicorn main:app --host 0.0.0.0 --port 8080"]
```

```dockerfile
# Frontend — React build served by Nginx (frontend/Dockerfile)
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

The backend container uses the ECS task IAM role for AWS credentials — no secrets in env vars or image.

---

## IAM Permission Boundaries

### Task Execution Role (shared)
```
ecr:GetAuthorizationToken        → *
ecr:BatchCheckLayerAvailability,
ecr:GetDownloadUrlForLayer,
ecr:BatchGetImage                → arn:aws:ecr:us-west-2:<account>:repository/payinvestigator-*
logs:CreateLogStream,
logs:PutLogEvents                → arn:aws:logs:us-west-2:<account>:log-group:/ecs/payinvestigator-*
```

### Backend Task Role
```
bedrock:InvokeModel  → arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-6*
s3:GetObject,
s3:ListBucket        → arn:aws:s3:::payinvestigator-mockdata-<account_id>
```

### GitHub Actions OIDC Role
```
ecr:GetAuthorizationToken              → *
ecr:BatchCheckLayerAvailability,
ecr:PutImage, ecr:InitiateLayerUpload,
ecr:UploadLayerPart,
ecr:CompleteLayerUpload                → arn:aws:ecr:us-west-2:<account>:repository/payinvestigator-*
ecs:RegisterTaskDefinition             → *
ecs:UpdateService,
ecs:DescribeServices,
ecs:DescribeTaskDefinition             → payinvestigator cluster + both services
iam:PassRole                           → task execution role + backend task role
```

---

## Confirmed Values

| Item | Value |
|---|---|
| GitHub repo | `adityataps/vista-hackathon-26` |
| Cloudflare Zone ID | `9a2b68936aec95fc2ad33a144cec981a` |
| Bedrock model access | Enabled in `us-west-2` ✓ |

## Remaining Pre-Apply Steps

- Add Cloudflare API token to `terraform.tfvars` as `cloudflare_api_token` (needs `Zone:DNS:Edit` for `tapshalkar.com`)
- Add `AWS_ACCOUNT_ID` to GitHub Secrets
- Add `backend/Dockerfile` and `frontend/Dockerfile` before first CI run
- Add `GET /health` endpoint to FastAPI before `terraform apply` (ALB health check depends on it)
