resource "aws_security_group" "orders_api" {
  name        = "${var.name_prefix}-api"
  description = "Ingress for the orders API."
  vpc_id      = var.vpc_id
  tags        = local.common_tags
}

resource "aws_vpc_security_group_ingress_rule" "orders_api_https" {
  security_group_id = aws_security_group.orders_api.id
  description       = "HTTPS from the office range."
  cidr_ipv4         = var.office_cidr
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  tags              = local.common_tags
}

resource "aws_vpc_security_group_egress_rule" "orders_api_all" {
  security_group_id = aws_security_group.orders_api.id
  description       = "Allow outbound."
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  tags              = local.common_tags
}
