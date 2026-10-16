# Worker nodes: an EKS managed node group.
#
# Two m7i-flex.large nodes (2 vCPU / 8 GiB each) run the app, Postgres, the ingress
# controller and the monitoring stack. They are On-Demand and Free Tier eligible, which
# is what an AWS Free plan account allows. On a paid account, node_capacity_type = "SPOT"
# costs roughly a third as much: if AWS reclaims a node, the managed group replaces it
# and Kubernetes reschedules the pods.
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-workers"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.public[*].id

  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = var.node_capacity_type
  instance_types = var.node_instance_types
  disk_size      = 20

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  # Replace nodes one at a time during upgrades, so the app keeps serving.
  update_config {
    max_unavailable = 1
  }

  labels = {
    "shelfwise.io/pool" = "general"
  }

  depends_on = [aws_iam_role_policy_attachment.node]

  lifecycle {
    # Let the cluster autoscaler or a manual scale change the size without Terraform
    # trying to undo it on the next plan.
    ignore_changes = [scaling_config[0].desired_size]
  }
}

# coredns and the EBS driver run as pods, so they wait for nodes to exist.
resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = "coredns"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "eks-pod-identity-agent"

  depends_on = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "aws-ebs-csi-driver"

  pod_identity_association {
    role_arn        = aws_iam_role.ebs_csi.arn
    service_account = "ebs-csi-controller-sa"
  }

  depends_on = [aws_eks_addon.pod_identity_agent]
}

# metrics-server feeds CPU usage to the HorizontalPodAutoscaler.
resource "aws_eks_addon" "metrics_server" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "metrics-server"

  depends_on = [aws_eks_node_group.main]
}
