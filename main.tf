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

# Google Cloud Secret Manager Resource
resource "google_secret_manager_secret" "api_key_secret" {
  secret_id = "gemini-api-key"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "api_key_version" {
  secret      = google_secret_manager_secret.api_key_secret.id
  secret_data = "dummy-secret-value-for-deployment"
}

# Cloud Run v2 Service with Secret Manager environment injection
resource "google_cloud_run_v2_service" "agent_service" {
  name     = "ticket-timing-agent"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "gcr.io/ai-course-assessment-project/ticket-agent:latest"
      
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_key_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}
