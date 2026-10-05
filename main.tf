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
  project = "ai-course-assessment-project"
  region  = "us-central1"
}

# 1. Mandatory IaC Resource: Google Cloud Secret Manager Secret
resource "google_secret_manager_secret" "api_secret" {
  secret_id = "gemini-api-key"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "api_secret_version" {
  secret      = google_secret_manager_secret.api_secret.id
  secret_data = "dummy-secret-value"
}

# 2. Mandatory IaC Resource: Cloud Run Service with Secret Manager Integration
resource "google_cloud_run_v2_service" "agent_service" {
  name     = "ticket-timing-agent"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/ai-course-assessment-project/ticket-agent:latest"

      # Explicit Secret Manager Environment Variable Injection
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}
