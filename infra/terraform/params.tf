data "aws_caller_identity" "current" {}

resource "aws_ssm_parameter" "database_url" {
  name  = "/docmind/DATABASE_URL"
  type  = "SecureString"
  value = "postgresql+psycopg://docmind:${random_password.db.result}@${aws_db_instance.docmind.address}:5432/docmind?sslmode=require"
}

# The node may read /docmind/* parameters - nothing else in Parameter Store
data "aws_iam_policy_document" "read_params" {
  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = ["arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/docmind/*"]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "read_params" {
  name   = "read-docmind-params"
  role   = aws_iam_role.k3s_node.id
  policy = data.aws_iam_policy_document.read_params.json
}
