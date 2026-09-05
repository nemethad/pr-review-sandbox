variable "region" {
  description = "Region the sandbox stack would be created in."
  type        = string
  default     = "eu-central-1"
}

variable "name_prefix" {
  description = "Prefix for every resource name."
  type        = string
  default     = "orders-sandbox"
}

variable "owner" {
  description = "Team accountable for these resources."
  type        = string
  default     = "orders-platform"
}

variable "office_cidr" {
  description = "CIDR range allowed to reach administrative ports."
  type        = string
  default     = "10.20.0.0/16"
}

variable "vpc_id" {
  description = "VPC the sandbox stack attaches to."
  type        = string
  default     = "vpc-00000000000000000"
}
