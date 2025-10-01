# RateMate TaaS VS Code Extension

Prototype extension that calls the orchestrator service to plan and generate tests directly from VS Code.

## Commands

- `TaaS: Generate Tests` – sends the active editor contents to the orchestrator and prints the generated patch in an output channel.

Configure the orchestrator endpoint via the `ORCHESTRATOR_URL` environment variable (default `http://localhost:8088`).
