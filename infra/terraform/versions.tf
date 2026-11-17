terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Sem backend remoto: o estado fica local e este modulo NAO e aplicado (ver docs/DECISIONS.md, D-07).
  # O CI roda apenas `fmt -check` + `validate` (sem credenciais da AWS).
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Nome do bucket precisa ser globalmente unico: o account id resolve sem random provider.
  raw_bucket_name = "${var.project}-${var.environment}-raw-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}
