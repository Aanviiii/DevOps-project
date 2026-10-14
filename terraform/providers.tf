# Credentials come from the standard AWS chain (aws configure / environment variables),
# never from this repository.
provider "aws" {
  region = var.region

  # Every resource is tagged, so the console and the bill show exactly what this
  # project created, and anything left over after destroy is easy to spot.
  default_tags {
    tags = {
      Project   = "shelfwise"
      ManagedBy = "terraform"
      Owner     = var.owner
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
  # Skip Local Zones and Wavelength zones, which EKS does not support.
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}
