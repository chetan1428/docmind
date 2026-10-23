import {
  to = aws_iam_openid_connect_provider.github
  id = "arn:aws:iam::975739936766:oidc-provider/token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
