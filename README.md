# VibeBridge

A local Mac agent and Chrome extension for AI-assisted development workflows.

## Architecture
- `agent/`: local Python HTTP service for project diagnostics and command execution.
- `extension/`: Chrome extension interface.
- The first milestone is a working local connection; direct integration with the exact active ChatGPT conversation requires separate compatibility work.

## Security
The agent binds only to localhost and requires a random bearer token. Project operations are restricted to configured project roots. Do not expose the local service to your network.
