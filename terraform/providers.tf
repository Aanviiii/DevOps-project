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

# Looked up only when availability_zones is left empty (see variables.tf).
data "aws_availability_zones" "available" {
  count = length(var.availability_zones) == 0 ? 1 : 0

  state = "available"
  # Skip Local Zones and Wavelength zones, which EKS does not support.
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}
