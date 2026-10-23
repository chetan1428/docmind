resource "aws_key_pair" "docmind" {
  key_name   = "docmind-tf"
  public_key = file("${path.module}/keys/docmind-tf.pub")
}

# Latest official Ubuntu 24.04 AMI, published by Canonical in SSM Parameter Store
data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "aws_instance" "k3s" {
  ami                    = data.aws_ssm_parameter.ubuntu_ami.insecure_value
  instance_type          = var.instance_type
  key_name               = aws_key_pair.docmind.key_name
  vpc_security_group_ids = [aws_security_group.k3s.id]
  iam_instance_profile   = aws_iam_instance_profile.k3s.name

  user_data                   = file("${path.module}/user_data.sh")
  user_data_replace_on_change = true

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = { Name = "docmind-k3s" }

  lifecycle {
    # A newer Ubuntu AMI must NOT silently replace (wipe) the running server
    ignore_changes = [ami]
  }
}

resource "aws_eip" "k3s" {
  instance = aws_instance.k3s.id
  domain   = "vpc"
  tags     = { Name = "docmind-k3s" }
}
