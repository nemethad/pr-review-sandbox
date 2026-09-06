resource "aws_cloudwatch_log_group" "orders_api" {
  name              = "/aws/orders/${var.name_prefix}"
  retention_in_days = 30
  tags              = local.common_tags
}
