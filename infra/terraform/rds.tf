resource "random_password" "db" {
  length  = 32
  special = false # no @ : / # -> safe inside a connection URL
}

resource "aws_security_group" "rds" {
  name        = "docmind-rds"
  description = "DocMind RDS - only reachable from the k3s node"
  tags        = { Name = "docmind-rds" }
}

resource "aws_vpc_security_group_ingress_rule" "pg_from_k3s" {
  security_group_id            = aws_security_group.rds.id
  description                  = "Postgres from the k3s node SG only"
  referenced_security_group_id = aws_security_group.k3s.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_db_instance" "docmind" {
  identifier     = "docmind-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "docmind"
  username = "docmind"
  password = random_password.db.result

  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 1
  skip_final_snapshot     = true  # practice env: no snapshot on destroy
  deletion_protection     = false # practice env: allow terraform destroy
  apply_immediately       = true

  lifecycle {
    # AWS auto-applies minor upgrades (16.x) - do not fight them
    ignore_changes = [engine_version]
  }
}
