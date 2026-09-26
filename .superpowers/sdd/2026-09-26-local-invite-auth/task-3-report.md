# Auth Plan Task 3 report

## Implemented

- `/auth/login` serves the SPA shell. Local sign-in uses the same-origin API and secure server session cookies; the UI has no HCA control. The identity-less runtime leaves `/auth/callback` absent.
- Invite signup reads only `#invite=...`, sends the token in the signup POST body, and clears the fragment after successful account creation.
- Operator invite controls configure maximum uses and expiry (defaults: 5 and 7 days), show use/expiry/status, identify email-bound legacy invitations, and require confirmation before revocation.
- Developer invite status exposes the enduring entitlement, `can_issue`, issuance time, and safe invite metadata. The raw link is revealed in page memory at creation and is not returned by the status API.
- README and deploy guidance describe local operator bootstrap/recovery and mark HCA integration dormant.

## Verification

Frontend commands (final runs):

```text
npm run test -- --reporter=dot
> sponsored-provider-portal@0.1.0 test
> vitest run --reporter=dot
RUN v5.0.2
Test Files  2 passed (2)
Tests       5 passed (5)
exit code 0

npm run lint
> sponsored-provider-portal@0.1.0 lint
> oxlint src vite.config.ts oxlint.config.ts
exit code 0

npm run typecheck
> sponsored-provider-portal@0.1.0 typecheck
> tsc --noEmit
exit code 0

npm run build
> sponsored-provider-portal@0.1.0 build
> tsc -b && vite build
vite v7.3.6 building client environment for production...
✓ 1653 modules transformed.
dist/assets/index-CqTGix2G.css  40.34 kB │ gzip: 8.12 kB
dist/assets/index-DuzMy024.js 399.53 kB │ gzip: 121.01 kB
✓ built in 5.15s
exit code 0
```

Python 3.11 runs after the API changes:

```text
py -3.11 -m pytest tests/test_portal_api.py tests/test_portal_auth.py tests/test_portal_local_auth.py tests/test_portal_db_catalog.py tests/test_portal_gateway.py -q
86 passed, 1 warning in 16.31s

py -3.11 -m pytest -q
122 passed, 1 warning in 22.90s
```

Both Python runs emitted the Starlette deprecation warning that `httpx` through `starlette.testclient` is deprecated and suggests installing `httpx2`.

Component coverage checks local login and generic failures, autocomplete labels, keyboard-accessible password reveal, fragment-only invite signup and role routing, operator default limits and confirmed revocation, and developer one-time link visibility followed by token-free status after remount. API coverage checks configurable/default uses, revoke response/status, one-time developer entitlement and consumed state, and absence of the raw token from status. The identity-less runtime test asserts `/auth/callback` returns 404.

## Visual check

The controller captured and inspected the isolated 4175 desktop preview: sign-in, fragment-based signup, and the operator invite dialog. The operator dialog was clean at desktop size. No phone screenshot was captured, so phone-size visual QA is not claimed. The auth layout CSS includes single-column sizing, safe-area padding, and mobile-sized controls; those rules have not been visually captured at phone dimensions.

## Scope and publication

The locked design tokens and styles were preserved. No deployment, Nest, service restart, or push was performed. The Task 3 frontend, invite API/database changes, the isolated `GET /auth/login` shell route, and local-auth README section are in `d59d06d`. This report and the deploy auth/cutover runbook are committed in the documentation follow-up. Other dirty README and `app/main.py` hunks remain unstaged.
