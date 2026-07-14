# AWS Infrastructure Design — PayInvestigator
**Date:** 2026-07-14  
**Region:** `us-west-2`  
**Domain:** `vistahack26.tapshalkar.com` (Cloudflare DNS)

---

## Architecture Overview

```
GitHub (push to main)
        │
        ▼
GitHub Actions (OIDC → AWS)
  1. Build backend image  → push to ECR (payinvestigator-backend)
  2. Build frontend image → push to ECR (payinvestigator-frontend)
  3. SSH into EC2 → docker compose pull && docker compose up -d
        │
        ▼
EC2 t3.medium (us-west-2)  ←── Elastic IP
  ┌─────────────────────────────────────┐
  │  Nginx (port 80)                    │
  │    /api/* → FastAPI :8080           │
  │    /*     → React static files      │
  │                                     │
  │  FastAPI + LangGraph (:8080)        │
  │    ├── pulls mock data from S3      │
  │    └── calls Bedrock (claude-sonnet-4-6)    │
  └─────────────────────────────────────┘
        │
        ▼
Cloudflare DNS (proxied, orange cloud)
  vistahack26.tapshalkar.com → Elastic IP
  Cloudflare terminates HTTPS; forwards HTTP to EC2:80
  SSL mode: Full
```

---

## AWS Resources

| Resource | Name / Details |
|---|---|
| `aws_instance` | `t3.medium`, Amazon Linux 2023, `us-west-2a`. User data installs Docker, Docker Compose, AWS CLI; logs into ECR on boot. |
| `aws_eip` | Elastic IP attached to instance. Cloudflare A record points here. |
| `aws_security_group` | Inbound: 80 from Cloudflare IP ranges; 22 from `0.0.0.0/0` (SSH for GitHub Actions). Outbound: all. |
| `aws_ecr_repository` | `payinvestigator-backend` — image lifecycle: keep last 5. |
| `aws_ecr_repository` | `payinvestigator-frontend` — image lifecycle: keep last 5. |
| `aws_s3_bucket` | `payinvestigator-mockdata-<account_id>` — private, versioning off. Holds JSON mock data files seeded into SQLite on container startup. |
| `aws_iam_role` (EC2) | Instance profile. Policies: `s3:GetObject` + `s3:ListBucket` on mock data bucket; `bedrock:InvokeModel` on `claude-sonnet-4-6` ARN. |
| `aws_iam_role` (GitHub Actions) | OIDC trust: `repo:AdityaTapshalkar/vista-hackathon-26:ref:refs/heads/main`. Policies: `ecr:GetAuthorizationToken`; `ecr:BatchCheckLayerAvailability`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload` on both repos; `ec2:DescribeInstances` (resolve EIP). |
| `aws_iam_openid_connect_provider` | GitHub Actions OIDC provider (`token.actions.githubusercontent.com`). |
| `aws_key_pair` | `payinvestigator-deploy` — public key managed in Terraform; private key stored as `EC2_SSH_PRIVATE_KEY` GitHub Secret. |
| `cloudflare_record` | A record, name `vistahack26`, value = Elastic IP, proxied = `true`. |

---

## Terraform Layout

```
infra/
├── main.tf           # provider config (aws + cloudflare), backend
├── variables.tf      # region, account_id, cloudflare_zone_id, cloudflare_api_token, ssh_public_key
├── outputs.tf        # elastic_ip, ecr_backend_url, ecr_frontend_url, s3_bucket_name
├── ec2.tf            # aws_instance, aws_eip, aws_eip_association, aws_key_pair
├── security_group.tf # aws_security_group (cloudflare IPs + SSH)
├── ecr.tf            # aws_ecr_repository x2, aws_ecr_lifecycle_policy x2
├── s3.tf             # aws_s3_bucket, aws_s3_bucket_public_access_block
├── iam.tf            # EC2 instance profile + role; GitHub Actions OIDC role
└── dns.tf            # cloudflare_record
```

Terraform state: local `terraform.tfstate` for the hackathon (no S3 backend needed).  
Sensitive vars (`cloudflare_api_token`, `ssh_public_key`) passed via `terraform.tfvars` (gitignored).

---

## GitHub Actions Pipeline

**File:** `.github/workflows/deploy.yml`  
**Trigger:** push to `main`

```yaml
steps:
  1. actions/checkout
  2. aws-actions/configure-aws-credentials (OIDC, role = GitHub Actions IAM role ARN)
  3. aws-actions/amazon-ecr-login
  4. Build backend Docker image; tag :latest + :<git-sha>; push both tags to ECR
  5. Build frontend Docker image; tag :latest + :<git-sha>; push both tags to ECR
  6. SSH into EC2 (appleboy/ssh-action, key = EC2_SSH_PRIVATE_KEY secret)
     a. aws ecr get-login-password | docker login ...
     b. docker compose pull
     c. docker compose up -d
     d. docker image prune -f
```

**GitHub Secrets required:**
- `AWS_ACCOUNT_ID`
- `EC2_HOST` (Elastic IP)
- `EC2_SSH_PRIVATE_KEY`
- `EC2_SSH_USER` (`ec2-user`)

---

## docker-compose.yml (on EC2)

```yaml
services:
  backend:
    image: <account>.dkr.ecr.us-west-2.amazonaws.com/payinvestigator-backend:latest
    ports:
      - "8080:8080"
    environment:
      - AWS_DEFAULT_REGION=us-west-2
      - S3_BUCKET=payinvestigator-mockdata-<account_id>
    restart: unless-stopped

  frontend:
    image: <account>.dkr.ecr.us-west-2.amazonaws.com/payinvestigator-frontend:latest
    ports:
      - "3000:80"
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
```

The `backend` container uses the EC2 instance profile for AWS credentials — no secrets in env vars.

---

## Nginx Config (nginx.conf on EC2)

```nginx
server {
    listen 80;

    location /api/ {
        proxy_pass http://backend:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://frontend:80/;
        proxy_set_header Host $host;
    }
}
```

---

## EC2 User Data (bootstrap script)

On first boot:
1. Install Docker + Docker Compose plugin
2. Add `ec2-user` to the `docker` group
3. Install AWS CLI v2
4. Log into ECR
5. Place `docker-compose.yml` and `nginx.conf` in `/home/ec2-user/app/`
6. Run `docker compose up -d`

The compose file and nginx config are either baked into the user data or pulled from S3.

---

## TLS / Cloudflare Setup

- Cloudflare DNS A record for `vistahack26.tapshalkar.com` → Elastic IP, **proxied** (orange cloud)
- SSL/TLS mode in Cloudflare dashboard: **Flexible** (Cloudflare ↔ browser is HTTPS; Cloudflare ↔ EC2 is HTTP on port 80 — no cert on EC2 required). Use Full only if you add a self-signed cert to Nginx.
- Security group allows port 80 from [Cloudflare published IP ranges](https://www.cloudflare.com/ips/) only — direct non-Cloudflare access to EC2:80 is blocked. Port 443 on EC2 is not used (Cloudflare handles TLS).

---

## IAM Permission Boundaries

### EC2 Instance Profile
```
s3:GetObject, s3:ListBucket → arn:aws:s3:::payinvestigator-mockdata-*
bedrock:InvokeModel          → arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-6*
```

### GitHub Actions OIDC Role
```
ecr:GetAuthorizationToken    → *
ecr:BatchCheckLayerAvailability,
ecr:PutImage,
ecr:InitiateLayerUpload,
ecr:UploadLayerPart,
ecr:CompleteLayerUpload      → arn:aws:ecr:us-west-2:<account>:repository/payinvestigator-*
ec2:DescribeInstances        → *
```

---

## Confirmed Values

| Item | Value |
|---|---|
| GitHub repo | `adityataps/vista-hackathon-26` |
| Cloudflare Zone ID | `9a2b68936aec95fc2ad33a144cec981a` |
| Bedrock model access | Enabled in `us-west-2` ✓ |

## Remaining Pre-Apply Steps

- Generate SSH keypair locally; add public key to `terraform.tfvars` as `ssh_public_key`
- Add Cloudflare API token to `terraform.tfvars` as `cloudflare_api_token` (needs `Zone:DNS:Edit` permission for `tapshalkar.com`)
- Set Cloudflare SSL/TLS mode to **Flexible** in the dashboard for `tapshalkar.com` before first deploy
