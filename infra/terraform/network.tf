# Look up my current public IP so SSH is only open to me
data "http" "my_ip" {
  url = "https://checkip.amazonaws.com"
}

locals {
  my_cidr = "${chomp(data.http.my_ip.response_body)}/32"
}

resource "aws_security_group" "k3s" {
  name        = "docmind-k3s"
  description = "DocMind k3s node"
  tags        = { Name = "docmind-k3s" }
}

resource "aws_vpc_security_group_ingress_rule" "ssh_from_me" {
  security_group_id = aws_security_group.k3s.id
  description       = "SSH from my IP only"
  cidr_ipv4         = local.my_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "http_public" {
  security_group_id = aws_security_group.k3s.id
  description       = "Public website"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

# Terraform REMOVES AWS's default "allow all outbound" rule, so add it back explicitly
resource "aws_vpc_security_group_egress_rule" "all_out" {
  security_group_id = aws_security_group.k3s.id
  description       = "All outbound (packages, ECR, SSM, Groq)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
