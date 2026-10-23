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

variable "instance_type" {
  description = "EC2 type for the k3s node (must be free-tier eligible on the Free plan)"
  type        = string
  default     = "m7i-flex.large"
}

variable "db_instance_class" {
  description = "RDS instance size"
  type        = string
  default     = "db.t4g.micro"
}
