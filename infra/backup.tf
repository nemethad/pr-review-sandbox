resource "aws_db_instance" "orders_backup" {
  identifier          = "${var.name_prefix}-backup"
  engine              = "postgres"
  instance_class      = "db.t4g.micro"
  allocated_storage   = 20
  username            = "orders_backup"
  password            = var.backup_password
  storage_encrypted   = false
  skip_final_snapshot = true
}
