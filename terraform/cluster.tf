resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = aws_subnet.public[*].id
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = var.api_allowed_cidrs
  }

  # Cluster access is managed through EKS access entries rather than the old aws-auth
  # ConfigMap, and whoever runs `terraform apply` becomes cluster admin.
  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  # Do not slide into paid extended support if the cluster outlives its version.
  upgrade_policy {
    support_type = "STANDARD"
  }

  # Control-plane logs go to CloudWatch, which bills per GB. Off for this demo cluster.
  enabled_cluster_log_types = []

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

# Core add-ons managed by EKS. vpc-cni, kube-proxy and coredns would be installed
# anyway; declaring them lets Terraform own their versions.
resource "aws_eks_addon" "core" {
  for_each = toset(["vpc-cni", "kube-proxy"])

  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = each.value
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}
