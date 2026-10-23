import {
  to = aws_ecr_repository.docmind
  id = "docmind"
}

resource "aws_ecr_repository" "docmind" {
  name                 = "docmind"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the 20 most recent images so storage never grows forever
resource "aws_ecr_lifecycle_policy" "docmind" {
  repository = aws_ecr_repository.docmind.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
