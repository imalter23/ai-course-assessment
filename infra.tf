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

# Secret Manager Resource for Secure API Key Injection
resource "google_secret_manager_secret" "gemini_api_key_secret" {
  secret_id = "gemini-api-key"
  replication {
    automatic = true
  }
}

resource "google_cloud_run_v2_service" "agent_service" {
  name     = "ticket-timing-agent"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/${var.project_id}/ticket-agent:latest"
      
      # Secure Secret Manager Environment Injection
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}
