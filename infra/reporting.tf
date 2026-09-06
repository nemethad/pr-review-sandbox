resource "aws_iam_user" "reporting" {
  name = "${var.name_prefix}-reporting"
  tags = local.common_tags
}

resource "aws_iam_access_key" "reporting" {
  user = aws_iam_user.reporting.name
}

resource "aws_iam_user_policy" "reporting" {
  name   = "archive-read"
  user   = aws_iam_user.reporting.name
  policy = data.aws_iam_policy_document.orders_api_archive_read.json
}
