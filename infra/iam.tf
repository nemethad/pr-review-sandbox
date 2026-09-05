data "aws_iam_policy_document" "orders_api_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "orders_api" {
  name               = "${var.name_prefix}-api"
  assume_role_policy = data.aws_iam_policy_document.orders_api_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "orders_api_archive_read" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.orders_archive.arn}/*"]
  }
}

resource "aws_iam_role_policy" "orders_api_archive_read" {
  name   = "archive-read"
  role   = aws_iam_role.orders_api.id
  policy = data.aws_iam_policy_document.orders_api_archive_read.json
}
