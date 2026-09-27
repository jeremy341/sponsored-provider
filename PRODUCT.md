# Product facts: Sponsored Provider

## Product

Sponsored Provider is an invite-only, student-scale OpenAI-compatible AI gateway. The operator connects arbitrary OpenAI-compatible upstreams and sponsors usage for invited Hack Club users. A developer creates personal API keys, selects the approved model catalog, and inspects only their own usage.

## Confirmed users and jobs

- **Operator:** connect upstream profiles, sync/approve/prices models, invite and manage users, set global and per-user safeguards, inspect aggregate activity, and respond to abuse.
- **Developer:** create a local username/password account with an invite, manage personal API keys and model selections, call the stable `/v1` endpoint, and inspect personal request/activity and allowance.

## Confirmed access and usage rules

- Initial onboarding is invite-only; public self-registration is out of scope.
- Each developer may issue one single-use invite to share. An operator may issue a configurable multi-use invite with an expiry/revocation control.
- A user's daily or weekly allowance and user-wide RPM are assigned by the operator and shared across all of that user's keys.
- A developer may configure only a stricter per-key spend or RPM ceiling.
- New upstream models remain unavailable until an operator approves them and configures usable pricing. Default key policy is all approved models.
- Upstream credentials are write-only in the UI and encrypted at rest. Prompts and completions are not stored.
- Request, token, latency, and estimated-cost history is append-only and remains available after access is disabled or archived.
- Missing provider usage/pricing is unknown or estimated, never silently shown as zero/free.

## Confirmed architecture and design

- One FastAPI deployment serves a React/Vite static SPA and the existing OpenAI-compatible `/v1` API.
- SQLite is retained for the invite-only, single-process pilot with additive migrations and tested backups.
- Local username/password sessions are separate from bearer API keys. Hack Club Auth code and historical documentation are retained but its routes and UI are dormant.
- The visual system is the approved technical/utilitarian identity in `.ulpi/design/DESIGN.md` and `.ulpi/design/provider-portals.md`.

## Explicit non-goals

No payments or wallet resale, open registration, marketplace, prompt storage, chat history, files/RAG/tools, automatic cross-provider fallback, or native non-OpenAI protocols in the first release.

## Known rollout gate

The initial local-account operator must be bootstrapped through the protected CLI. Do not deploy or replace the existing Nest service until backup/restore, backwards compatibility, operational ownership, and rollback have been reviewed.
