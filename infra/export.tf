resource "aws_s3_bucket" "metrics_export" {
  bucket = "${var.name_prefix}-metrics-export"
  tags   = local.common_tags
}

resource "aws_s3_bucket_ownership_controls" "metrics_export" {
  bucket = aws_s3_bucket.metrics_export.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "metrics_export" {
  depends_on = [aws_s3_bucket_ownership_controls.metrics_export]
  bucket     = aws_s3_bucket.metrics_export.id
  acl        = "public-read"
}

data "aws_iam_policy_document" "metrics_exporter" {
  statement {
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "metrics_exporter" {
  name   = "metrics-export"
  role   = aws_iam_role.orders_api.id
  policy = data.aws_iam_policy_document.metrics_exporter.json
}
