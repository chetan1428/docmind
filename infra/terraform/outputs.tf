output "ecr_repository_url" {
  value = aws_ecr_repository.docmind.repository_url
}

output "public_ip" {
  value = aws_eip.k3s.public_ip
}

output "app_url" {
  value = "http://${aws_eip.k3s.public_ip}.nip.io"
}

output "ssh_command" {
  value = "ssh -i ~/.ssh/docmind-tf ubuntu@${aws_eip.k3s.public_ip}"
}

output "instance_id" {
  value = aws_instance.k3s.id
}

output "rds_endpoint" {
  value = aws_db_instance.docmind.address
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}
