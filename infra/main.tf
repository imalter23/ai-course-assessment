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
  region  = var.region
}

# Explicit Google Cloud Secret Manager Resource for API Key
resource "google_secret_manager_secret" "gemini_secret" {
  secret_id = "gemini-api-key"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "gemini_secret_version" {
  secret      = google_secret_manager_secret.gemini_secret.id
  secret_data = "placeholder-key-for-evaluation"
}

# Cloud Run v2 Service with Secret Manager Injection
resource "google_cloud_run_v2_service" "ticket_agent_service" {
  name     = "ticket-timing-agent"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/${var.project_id}/ticket-agent:latest"

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}
