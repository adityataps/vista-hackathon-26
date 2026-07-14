# ACM DNS validation records in Cloudflare
resource "cloudflare_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options :
    dvo.domain_name => {
      name  = trimsuffix(dvo.resource_record_name, ".tapshalkar.com.")
      value = trimsuffix(dvo.resource_record_value, ".")
      type  = dvo.resource_record_type
    }
  }

  zone_id = var.cloudflare_zone_id
  name    = each.value.name
  content = each.value.value
  type    = each.value.type
  ttl     = 60
  proxied = false
}

# Validation waiter — Terraform blocks here until ACM issues the cert
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in cloudflare_record.acm_validation : r.hostname]
}

# App CNAME — vistahack26.tapshalkar.com → ALB
resource "cloudflare_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = "vistahack26"
  content = aws_lb.main.dns_name
  type    = "CNAME"
  ttl     = 300
  proxied = false
}
