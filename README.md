# GradrAI MCP Server

This is the custom Model Context Protocol (MCP) server for GradrAI, providing tools for question parsing, marking guide structuring, answer normalization, and triggering the ALOC cache.

## Overview
This server is built using the `mcp[cli]` (FastMCP) and `google-genai` libraries. It exposes tools securely over HTTP (using the `streamable-http` transport).

## Available Tools
- `parse_questions`: Parses raw question text into a structured list.
- `parse_marking_guide`: Converts raw marking guide text into a structured rubric using Gemini.
- `normalize_answers`: Normalizes student answers (lowercasing, removing noise).
- `trigger_aloc_cache`: Triggers the GradrAI Node.js backend to seed and cache past questions from the ALOC API.

## Local Setup (for Hackathon Judges)
To run this MCP server locally on your machine:

1. **Install dependencies**:
   Ensure you have Python 3.10+ and `uv` installed.
   ```bash
   uv sync
   ```

2. **Environment Variables**:
   Create a `.env` file or export the following variables:
   ```bash
   export PORT=8080
   export GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
   export GOOGLE_CLOUD_LOCATION=us-central1
   export GRADR_BACKEND_URL=http://localhost:5000
   export ADMIN_JWT_TOKEN=<your-admin-token>
   ```
   *Make sure you are authenticated with GCP (`gcloud auth application-default login`) since `parse_marking_guide` uses Vertex AI.*

3. **Run the server**:
   ```bash
   uv run server.py
   ```
   The server will start and listen on port 8080.

## Deployment
This MCP server is deployed to Google Cloud Run. 

**Deployed URL**: 
`https://gradrmcp-943768265988.us-central1.run.app`

*(Note: If you want to connect a local agent to this deployed MCP, ensure you have IAM permissions and pass a valid OIDC token as configured in `toolsets.py`)*
