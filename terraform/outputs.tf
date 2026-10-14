output "region" {
  description = "Region the cluster runs in."
  value       = var.region
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "Kubernetes version running on the control plane."
  value       = aws_eks_cluster.main.version
}

output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnets, one per availability zone."
  value       = aws_subnet.public[*].id
}

output "configure_kubectl" {
  description = "Run this to point kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.main.name}"
}

output "node_group" {
  description = "Managed node group name, capacity type and instance types."
  value = {
    name           = aws_eks_node_group.main.node_group_name
    capacity_type  = aws_eks_node_group.main.capacity_type
    instance_types = aws_eks_node_group.main.instance_types
  }
}
