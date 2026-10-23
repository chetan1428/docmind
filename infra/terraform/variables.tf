variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "github_repo" {
  description = "GitHub repo allowed to deploy (owner/name)"
  type        = string
  default     = "chetan1428/docmind"
}
