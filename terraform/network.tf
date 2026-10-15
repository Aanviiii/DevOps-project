# A small VPC with public subnets only.
#
# The usual production layout puts worker nodes in private subnets behind a NAT
# gateway. A NAT gateway costs about $1.10 a day before any traffic, more than the
# nodes themselves for a short-lived demo cluster. Here nodes sit in public subnets
# with public IPs, and their security group (managed by EKS) admits only traffic
# from the cluster itself, so nothing on the nodes is reachable from the internet.

locals {
  # Pinned zones when given, otherwise whatever AWS reports as available in the region.
  azs = slice(
    length(var.availability_zones) > 0 ? var.availability_zones : data.aws_availability_zones.available[0].names,
    0,
    var.az_count,
  )
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true # required for EKS nodes to register with the cluster

  tags = { Name = "${var.cluster_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.cluster_name}-igw" }
}

resource "aws_subnet" "public" {
  count = var.az_count

  vpc_id                  = aws_vpc.main.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index) # /20 each: 4,096 addresses
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.cluster_name}-public-${local.azs[count.index]}"
    # Tells the AWS load balancer integration it may place internet-facing LBs here.
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.cluster_name}-public" }
}

resource "aws_route_table_association" "public" {
  count = var.az_count

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
