variable "region" {
  default = "us-west-2"
}

variable "aws_profile" {
  default = "default"
}

variable "app_name" {
  default = "payinvestigator"
}

variable "domain" {
  default = "vistahack26.tapshalkar.com"
}

variable "cloudflare_zone_id" {
  default = "9a2b68936aec95fc2ad33a144cec981a"
}

variable "cloudflare_api_token" {
  sensitive = true
}

variable "backend_url" {
  description = "HTTPS URL of the PayInvestigator backend (ALB)"
  type        = string
  default     = ""
}
