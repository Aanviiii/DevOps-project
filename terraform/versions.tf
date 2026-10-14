terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.69"
    }
  }

  # State stays local on purpose: this cluster lives for one demo session and is
  # destroyed straight after, so a remote S3 backend would cost more setup than it
  # saves. *.tfstate is git-ignored because state contains resource IDs and secrets.
}
