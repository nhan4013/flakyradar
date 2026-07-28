terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ponytail: skeleton only, not wired to apply — fill in before Phase 4 deploy

resource "aws_s3_bucket" "raw_reports" {
  bucket = "${var.project_name}-raw-reports"
}

resource "aws_sqs_queue" "jobs" {
  name = "${var.project_name}-jobs"
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}
