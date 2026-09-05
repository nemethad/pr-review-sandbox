resource "aws_s3_bucket" "orders_archive" {
  bucket = "${var.name_prefix}-archive"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "orders_archive" {
  bucket = aws_s3_bucket.orders_archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "orders_archive" {
  bucket = aws_s3_bucket.orders_archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_versioning" "orders_archive" {
  bucket = aws_s3_bucket.orders_archive.id

  versioning_configuration {
    status = "Enabled"
  }
}
