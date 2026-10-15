variable "region" {
  description = "AWS region for every resource."
  type        = string
  default     = "ap-south-1"
}

variable "owner" {
  description = "Tag value naming who owns these resources."
  type        = string
  default     = "aanvi"
}

variable "cluster_name" {
  description = "Name of the EKS cluster (also prefixes the VPC and IAM roles)."
  type        = string
  default     = "shelfwise"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.cluster_name))
    error_message = "Use 3-31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Keep it in standard support: extended support costs six times as much per hour."
  type        = string
  default     = "1.35"
}

variable "vpc_cidr" {
  description = "Address range for the VPC. Each public subnet takes a /20 from it."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "az_count" {
  description = "How many availability zones (one public subnet each). EKS needs at least two."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "availability_zones" {
  description = <<-EOT
    Zones to place the subnets in, e.g. ["ap-south-1a", "ap-south-1b"]. Leave empty to ask
    AWS which zones are available (needs ec2:DescribeAvailabilityZones). Pinning them lets
    `terraform plan` run in an account that cannot call EC2 yet; apply works either way.
  EOT
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.availability_zones) == 0 || length(var.availability_zones) >= var.az_count
    error_message = "List at least az_count zones, or leave availability_zones empty."
  }
}

variable "api_allowed_cidrs" {
  description = "Networks allowed to reach the Kubernetes API endpoint. Narrow this to your own IP (x.x.x.x/32) where possible."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_instance_types" {
  description = "Instance types for the worker nodes. Several similar types make Spot capacity easier to find."
  type        = list(string)
  default     = ["t3.medium", "t3a.medium"]
}

variable "node_capacity_type" {
  description = "SPOT (about 70% cheaper, may be reclaimed) or ON_DEMAND."
  type        = string
  default     = "SPOT"

  validation {
    condition     = contains(["SPOT", "ON_DEMAND"], var.node_capacity_type)
    error_message = "node_capacity_type must be SPOT or ON_DEMAND."
  }
}

variable "node_desired_size" {
  description = "Worker nodes to start with."
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Fewest worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Most worker nodes."
  type        = number
  default     = 3
}

variable "budget_limit_usd" {
  description = "Monthly cost budget in USD. An email alert fires at 50% and 100% of it."
  type        = number
  default     = 5
}

variable "budget_alert_email" {
  description = "Where budget alerts go. Leave empty to skip creating the budget."
  type        = string
  default     = ""
}
