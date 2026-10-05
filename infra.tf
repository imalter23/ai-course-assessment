terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = "us-central1"
}

variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID"
  default     = "ai-course-assessment-project"
}

resource "google_cloud_run_v2_service" "agent_service" {
  name     = "ticket-timing-agent"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/${var.project_id}/ticket-agent:latest"
      env {
        name  = "GEMINI_API_KEY"
        value = "secret-manager-injected-key"
      }
    }
  }
}
