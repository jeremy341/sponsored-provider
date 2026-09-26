# Task 4: Security and integration verification report

Date: 2026-09-26
Worktree: `C:\Users\jerem\.codex\worktrees\provider-catalog-credits\provider`

## Verification results

- Full backend: `py -3.11 -m pytest -q -p no:cacheprovider` — **123 passed, 1 warning in 25.50s**. The warning is `StarletteDeprecationWarning`: using `httpx` with `starlette.testclient` is deprecated; it recommends `httpx2`.
- Frontend tests: `npm test` — **2 test files passed, 5 tests passed**.
- Frontend lint: `npm run lint` — **exit 0**.
- Frontend typecheck: `npm run typecheck` — **exit 0**.
- Frontend production build: `npm run build` — **exit 0**, Vite built successfully.
- Focused auth and OIDC checks: `py -3.11 -m pytest -q -p no:cacheprovider tests/test_portal_local_auth.py tests/test_portal_auth.py` — **40 passed, 1 warning in 7.25s** (same deprecation warning).

The first unprivileged attempts hit Windows `EPERM` when pytest created worktree fixtures, Vitest spawned esbuild, and TypeScript wrote build metadata. Re-running with elevated access resolved these environment restrictions. The final full backend result above is from the elevated run after the Task 4 test changes.

## Auth and logging checks

- Existing OIDC verifier tests pass. The verifier remains dormant in the active app: `app.main` configures `PortalService(identity=None)`. The active runtime integration test confirms `GET /auth/callback` returns **404**.
- The same runtime test confirms `POST /auth/bootstrap`, `/auth/adopt-operator`, and `/auth/reset` each return **404**. No remote bootstrap, adoption, or reset endpoint is mounted. The existing CLI test confirms first-operator bootstrap raises `PermissionError` when an operator already exists.
- Added a request-log secrecy test covering signup, login, and logout. Captured logs do not contain the submitted password, Argon2 password hash, raw invite token, session tokens, or CSRF tokens.
- The active app has no request-body logging call in its middleware or auth route handlers. Uvicorn access logs record paths/status, not request bodies or cookie/header values; credentials and invite tokens are sent in request bodies.

## Disposable database backup and restore

Passed on a uniquely named temporary database only. Output:

```text
PASS: disposable SQLite backup/restore; integrity_check=ok; operator row and password hash preserved; restored PortalDatabase reopened
PASS: removed disposable database directory after Python exited.
```

The backup and restored files were created under the system temp directory and removed after verification. No live database, runtime secrets, Nest service, or production environment was accessed or changed.

## Deployment documentation review

`deploy/README.md` and `README.md` already explain local bootstrap/adoption/reset commands, identify HCA as dormant with `/auth/callback` unmounted, describe persistent DB/runtime-secret backup and restore, and state that public cutover/restart requires a deliberate approval. No deployment or README edit was needed.

## Outcome

Task 4 verification is complete. The only reported warning is the existing Starlette/httpx TestClient deprecation notice. No production code or live service state was changed. Task 4 changes are limited to this report and auth test assertions.
