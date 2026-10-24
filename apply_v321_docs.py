#!/usr/bin/env python3
"""
Applies the v3.2.1 documentation edits to the repo.
Run from the repo root:  python apply_v321_docs.py

Two-phase and all-or-nothing: every anchor is checked first (each must be found
exactly once); only if all pass are the files written. Review with `git diff`.
Files: CHANGELOG.md, Issues_Encountered_and_Fixed.md, README.md,
       extension/README.md, CONTRIBUTING.md, api/openapi.yml, api-docs/openapi.yml
"""
import sys
from pathlib import Path

RELEASE_DATE = "2026-10-20"  # change if the merge date differs

CHANGELOG_ENTRY = """## [3.2.1] - @@DATE@@

Patch release: security hardening and small, certain bug fixes. No schema change and no analytics change. App v3.2.1 + Extension 1.0.1.

### Security

- **SSRF guard on interview-prep job description fetch** - `fetch_job_description` fetched any user-supplied URL, including whatever it redirected to. It now allows only http/https on ports 80 and 443, requires the host to resolve *only* to public addresses (private, loopback, link-local, reserved, IPv4-mapped IPv6 and numeric forms such as `2130706433` or `0x7f.1` are all rejected), and checks every redirect hop itself (max 3). Blocked fetches fall back silently to role + company questions. Known limit: urllib resolves the host again at connect time, so DNS rebinding between the check and the connect is not fully closed
- **API Gateway data tracing turned off** - `dataTraceEnabled` was on, which writes request/response bodies and Authorization headers (ID tokens, notes, contacts) to CloudWatch. Method logging at INFO, metrics and X-Ray are unchanged
- **Resume bucket CORS** restricted to the app's own origins plus localhost (was `*`)
- **PII in logs** - email addresses are masked in `cognito_verify` and `digest` logs
- **CSV formula injection** - exported cells starting with `=`, `+`, `-`, `@` are neutralised with a leading apostrophe; import reverses it so a round trip returns the original text

### Added

- **Daily cap on interview-prep generation** - default 10 per user per day (`PREP_DAILY_LIMIT`), separate counter `RATELIMIT#{userId}` / `PREPGEN#{date}` with a 2-day TTL. Returns 429 with `rateLimited: true`. Checked after the ownership test so unknown applications cannot burn quota. Fails open if the counter write fails, but logs at ERROR level (the chat limiter failed open silently for months in v3.1.1)
- **Shared pagination helper** - `shared/pagination.py` (`paginate_query`, `paginate_scan`) follows `LastEvaluatedKey`. Adopted in applications, insights, digest, followup, settings, notes and contacts, and as an S3 continuation loop in `list_resumes`. Previously every query/scan silently stopped at 1 MB
- **Monthly cost budget** - AWS Budgets, USD 20, covers the whole AWS account, notifies at 80% actual and 100% forecast
- **Input validation at create/update time** - `dateApplied` must be a real YYYY-MM-DD date; `jobDescUrl` must be http(s), max 2048 characters; resume `versionName` (max 64) and `filename` (max 128) cannot contain `/`, `\\` or control characters; upload `contentType` must be `application/pdf`; AI Coach `message` max 1000 characters. Stored data is never re-validated on read
- **Local development origin** - `http://localhost:5173` allowed in `ALLOWED_ORIGINS`, API Gateway CORS, Cognito callback/logout URLs and the Amplify OAuth config (resolves the long-deferred localhost CORS issue). Requests still require a valid JWT
- New `tests/test_pagination.py`, `frontend/src/test/csv.test.ts`, and new cases for the SSRF guard, redirect handling, the generate limiter, input validation, chat length and email masking

### Fixed

- Application detail modal: the Contacts section rendered inside the notes wrapper, so the "Add a note..." input appeared below Contacts. Contacts is now a sibling section
- Resume upload reported success on a failed S3 PUT, because `fetch` does not throw on 403/500. The response is now checked
- CSV import showed one "Application added" toast per row; it now shows only its summary toast
- CSV import split rows on `\\n`, so a note containing a line break broke the row. The parser now reads quoted fields across lines and accepts CRLF and a BOM
- `compute_patterns` listed `funnel`, `responseRateTimeSeries` and `statusHistory` twice, computing each twice. Duplicates removed
- OpenAPI referenced an undefined `CognitoJWT` security scheme on the v3.0 routes; now `cognitoAuth`
- Interview-prep generate showed a generic error toast even for a 429; it now shows the API message
- A resume `versionName` containing `/` broke `list_resumes` parsing

### Changed

- A job URL typed without `http://` or `https://` is now rejected with a clear message (editing an old record that still holds one fails until the URL is fixed)
- A blank `dateApplied` is treated as "not provided": new applications default to today, and clearing the field in the edit form leaves the stored date unchanged instead of writing an empty string
- Hardcoded test counts removed from README, CONTRIBUTING and the PR template
- `api/openapi.yml` and `api-docs/openapi.yml` bumped to 3.2.1 with the new constraints and the 429 response (both copies are kept; the docs UI is served from `api-docs/`)

### Extension 1.0.1

- Removed the unused `webNavigation` permission and the empty `externally_connectable` block from `manifest.json`
- Deleted dead `content-scripts/linkedin.css` and `shared.css`; corrected the stale "not yet verified" header in `glassdoor.js`

### Infrastructure

- Resume bucket CORS moved to `addCorsRule` with explicit origins
- API Gateway stage: `throttlingRateLimit` 20 and `throttlingBurstLimit` 40 (applied per method; starting values), `dataTraceEnabled` false
- `applytic-interview-prep` environment: `PREP_DAILY_LIMIT=10`
- New `MonthlyCostBudget` (AWS Budgets)
- New layer version (adds `pagination.py`)
- No new routes, tables or Lambdas

### Known limitations

- DNS rebinding between the SSRF check and the connect is not fully closed with urllib
- API Gateway's own 4xx/429 responses carry no CORS headers, so a throttled call looks like a network error in the browser (limits are generous; a `Default4xx` gateway response is the fix)
- `digest.get_active_users` is a filtered full-table scan; it is now complete but reads the whole table each Monday (a sparse GSI is planned for v4.0)
- The budget is account-wide, not per stack; throttle values are starting points

### Upgrade notes

- `cdk deploy` is required. `build_layer.sh` does not need re-running (no pip dependency changed)
- Reload the unpacked extension (or install the 1.0.1 zip); Chrome shows no prompt because only permissions were removed

**Commit scope:** `lambdas/`, `lambdas/shared_layer/`, `cdk/`, `frontend/src/`, `extension/`, `api/`, `api-docs/`, `tests/`, `docs`

---

"""

ISSUES = [
 ("Contacts section rendered inside the notes wrapper (v3.2.1)",
  "In `ApplicationDetailModal.tsx` the Contacts block sat inside the notes wrapper `<div>`, so the \"Add a note...\" input rendered below Contacts instead of directly under the notes list.",
  "Moved the add-note input up next to the notes list, closed the notes wrapper, and made Contacts a sibling section. Markup move only."),
 ("Failed resume uploads reported success (v3.2.1)",
  "`uploadResumeToS3` used `fetch`, which does not throw on a 403/500 response, so a rejected S3 PUT still showed the success toast.",
  "The response is now checked (`res.ok`) and an error is thrown, which the existing try/catch turns into the \"Upload failed\" toast."),
 ("CSV import showed one toast per row (v3.2.1)",
  "`handleImport` called `create()` for every row and each call fired \"Application added\", so a 50-row import produced 50 toasts on top of the summary toast.",
  "Added `createQuiet` to `useApplications` (same API call and cache update, no toast); the import path uses it and keeps its single summary toast."),
 ("CSV export allowed formula injection and import broke on multi-line notes (v3.2.1)",
  "Exported cells starting with `=`, `+`, `-` or `@` are executed as formulas by Excel and Sheets. Separately, import split the file on `\\n` before parsing, so a quoted note containing a line break was cut into several rows.",
  "Export prefixes such cells with an apostrophe and import strips it again, so a round trip returns the original text. The parser now reads the whole file as records (quoted newlines, CRLF and a BOM handled). A pure `buildCsv` function was split out so a round-trip test could run without a DOM."),
 ("compute_patterns listed three keys twice (v3.2.1)",
  "`funnel`, `responseRateTimeSeries` and `statusHistory` appeared twice in the returned dict (left over from merging v2.1 and v3.1 additions). Python kept the later value, but each was computed twice.",
  "Removed the duplicates. Output is unchanged."),
 ("OpenAPI referenced an undefined security scheme (v3.2.1)",
  "The v3.0 routes declared `security: - CognitoJWT: []`, but only `cognitoAuth` exists in `securitySchemes`, so Swagger UI showed the wrong auth for those routes.",
  "Renamed to `cognitoAuth` in both spec copies."),
 ("localhost blocked by CORS when running the frontend against the live backend (v3.2.1)",
  "Earlier deferred as Issue 28. `http://localhost:5173` was missing from the Lambda `ALLOWED_ORIGINS`, API Gateway CORS, and the Cognito callback/logout URLs, so `npm run dev` against the deployed API failed.",
  "Added the origin in all places (plus the Amplify OAuth config for Google sign-in on localhost). Every request still needs a valid JWT."),
 ("Job description fetch could be pointed at internal addresses (SSRF) (v3.2.1)",
  "`fetch_job_description` fetched any URL the user stored on an application and followed redirects without checking where they led, so a crafted URL (or a redirect) could make the Lambda request private, loopback or link-local addresses.",
  "Each hop is now validated before it is requested: http/https only, ports 80/443, no credentials in the URL, and the host must resolve only to public addresses (the check judges the resolved address, so numeric forms like `2130706433` and names resolving to private ranges are caught). Redirects are followed manually (max 3) with the same check on every hop. Known limit: urllib resolves again at connect time, so DNS rebinding is not fully closed."),
 ("Inputs were accepted without validation (v3.2.1)",
  "A resume `versionName` containing `/` broke `list_resumes` parsing; `dateApplied` and `jobDescUrl` accepted any string; uploads accepted any content type; chat messages had no length limit (token cost).",
  "Validators added at create/update time only (stored data is never rejected on read): real YYYY-MM-DD dates, http(s) URLs up to 2048 characters, S3-safe names, PDF-only uploads, chat messages up to 1000 characters."),
 ("Interview-prep generation had no usage limit (v3.2.1)",
  "Every call to generate (or regenerate) invokes Bedrock, with no per-user cap. The 429 that would have come back also showed only a generic toast.",
  "Daily cap of 10 per user (`PREP_DAILY_LIMIT`), checked after the ownership test, using its own counter. It fails open but logs at ERROR level, because the chat limiter's silent fail-open hid an IAM bug for months. The hook now shows the API's message."),
 ("Resume bucket allowed any origin (v3.2.1)",
  "The resume bucket's CORS rule used `allowedOrigins: ['*']`.",
  "Replaced with `addCorsRule` listing the CloudFront, GitHub Pages and custom-domain origins plus localhost. It has to be added after the CloudFront distribution is defined, since the domain is a token."),
 ("API Gateway logged request bodies and tokens, and had no throttling (v3.2.1)",
  "`dataTraceEnabled: true` makes the stage's execution log include request/response bodies and Authorization headers, so ID tokens and all notes and contacts landed in CloudWatch. No stage-level throttling was configured.",
  "`dataTraceEnabled` set to false, and stage-wide throttling of 20 requests/second with a burst of 40 added (applies per method)."),
 ("Email addresses were written to CloudWatch logs (v3.2.1)",
  "`cognito_verify` and `digest` logged full recipient emails.",
  "A local `_mask_email` helper (defined in each handler, not in `shared.middleware`, because the test stubs do not provide it) logs `h***@domain` instead."),
 ("Queries and scans silently stopped at 1 MB (v3.2.1)",
  "A single DynamoDB `query`/`scan` returns at most 1 MB and sets `LastEvaluatedKey` for the rest. Most handlers read only the first page, so large accounts would lose applications from lists, analytics and digests, and the digest/follow-up scans would skip users. `list_resumes` had the same limit at 1000 objects.",
  "New `shared/pagination.py` (`paginate_query`, `paginate_scan`) follows `LastEvaluatedKey` and is adopted across the handlers; `list_resumes` loops on the continuation token. It must not be used on calls that pass `Limit`. Because test files stub `shared.middleware` inline, the helper is registered in `tests/conftest.py`."),
 ("Hardcoded test counts drifted across documents (v3.2.1)",
  "README, CONTRIBUTING, the PR template and the knowledge file quoted 355, 410, 419 and 34 tests for the same suite at different times.",
  "Counts removed from the live docs; they point at the commands instead. Historical CHANGELOG entries keep the numbers they had at the time."),
 ("Extension shipped an unused permission and dead files (v3.2.1)",
  "After the popup-triggered redesign the manifest still requested `webNavigation` (a leftover of the iframe theory in Issue 52), carried an empty `externally_connectable` block, and `linkedin.css`/`shared.css` were unused. `glassdoor.js` still said its selectors were unverified.",
  "Removed the permission and block, deleted the CSS files, corrected the header, and bumped the extension to 1.0.1."),
]

def issues_text(start):
    out = []
    for i, (title, issue, fix) in enumerate(ISSUES):
        out.append(f"### {start + i}. {title}\n\n* **Issue:** {issue}\n\n* **Fix:** {fix}\n")
    return "\n" + "\n".join(out)

OPENAPI_EDITS = [
 ('  version: "3.1.1"', '  version: "3.2.1"'),
 ("""        message:
          type: string
          description: Trimmed server-side; rejects empty messages with 400.
""", """        message:
          type: string
          maxLength: 1000
          description: Trimmed server-side; rejects empty messages and messages over 1000 characters with 400.
"""),
 ("""        filename:
          type: string
          example: resume.pdf
        versionName:
          type: string
          default: v1
          example: v3-ml-focused
        contentType:
          type: string
          default: application/pdf
""", """        filename:
          type: string
          maxLength: 128
          example: resume.pdf
          description: v3.2.1. Must not contain "/" or "\\\\" or control characters.
        versionName:
          type: string
          maxLength: 64
          default: v1
          example: v3-ml-focused
          description: v3.2.1. Must not contain "/" or "\\\\" or control characters.
        contentType:
          type: string
          enum: [application/pdf]
          default: application/pdf
          description: v3.2.1. Only PDF uploads are supported.
"""),
 ("""        '404':
          $ref: '#/components/responses/NotFound'
        '500':
          $ref: '#/components/responses/InternalError'
""", """        '404':
          $ref: '#/components/responses/NotFound'
        '429':
          description: >
            Daily generation limit reached (10 per user per day by default,
            resets at UTC midnight).
          content:
            application/json:
              schema:
                type: object
                properties:
                  error:
                    type: string
                  rateLimited:
                    type: boolean
                    example: true
        '500':
          $ref: '#/components/responses/InternalError'
"""),
 ("""        jobDescUrl:
          type: string
          default: ""
""", """        jobDescUrl:
          type: string
          maxLength: 2048
          default: ""
          description: v3.2.1. Must start with http:// or https:// when provided; otherwise 400.
"""),
 ("""        jobDescUrl:
          type: string
        resumeVersion:
""", """        jobDescUrl:
          type: string
          maxLength: 2048
          description: v3.2.1. Must start with http:// or https:// when provided; otherwise 400.
        resumeVersion:
"""),
 ("          description: Defaults to today (server date) if omitted.\n",
  "          description: Defaults to today (server date) if omitted or blank. Must be a real YYYY-MM-DD date, otherwise 400.\n"),
 ("""        dateApplied:
          type: string
          format: date
        followUpDate:
""", """        dateApplied:
          type: string
          format: date
          description: v3.2.1. Must be a real YYYY-MM-DD date, otherwise 400. A blank value is ignored (the stored date is left unchanged).
        followUpDate:
"""),
]

def main():
    root = Path.cwd()
    plan = []  # (path, new_text)
    errors = []

    def load(rel):
        p = root / rel
        if not p.exists():
            errors.append(f"{rel}: file not found")
            return None, p
        return p.read_text(encoding="utf-8"), p

    def replace_once(text, old, new, label):
        n = text.count(old)
        if n != 1:
            errors.append(f"{label}: expected 1 match, found {n}: {old.strip()[:70]!r}")
            return text
        return text.replace(old, new)

    # CHANGELOG: insert above the 3.2.0 entry
    t, p = load("CHANGELOG.md")
    if t is not None:
        t = replace_once(t, "## [3.2.0] - 2026-10-11", CHANGELOG_ENTRY.replace("@@DATE@@", RELEASE_DATE) + "## [3.2.0] - 2026-10-11", "CHANGELOG.md")
        plan.append((p, t))

    # Issues file: append after the last entry (continue numbering)
    t, p = load("Issues_Encountered_and_Fixed.md")
    if t is not None:
        import re
        nums = [int(m) for m in re.findall(r"^### (\d+)\.", t, flags=re.M)]
        start = (max(nums) + 1) if nums else 1
        plan.append((p, t.rstrip("\n") + "\n" + issues_text(start)))
        print(f"Issues file: appending #{start} to #{start + len(ISSUES) - 1}")

    # README
    t, p = load("README.md")
    if t is not None:
        t = replace_once(t, "badge/version-v3.2.0-534ab7", "badge/version-v3.2.1-534ab7", "README badge")
        t = replace_once(t, "**Current version:** v3.2.0 (Browser Extension) - released October 2026",
                         "**Current version:** v3.2.1 (Security & Surgical Fixes) - released October 2026", "README current version")
        t = replace_once(t, "[Download the extension (v1.0.0)]", "[Download the extension (v1.0.1)]", "README extension link")
        plan.append((p, t))

    # extension README
    t, p = load("extension/README.md")
    if t is not None:
        t = replace_once(t, "**Version:** 1.0.0", "**Version:** 1.0.1", "extension README version")
        plan.append((p, t))

    # CONTRIBUTING: add conventions under Python code style
    t, p = load("CONTRIBUTING.md")
    if t is not None:
        anchor = "- All new Lambda routes need corresponding unit tests in `tests/`"
        extra = (anchor + "\n"
                 "- DynamoDB `query`/`scan` calls without `Limit` must go through `shared.pagination` (`paginate_query` / `paginate_scan`): a single call silently stops at 1 MB. Any new shared helper must also be registered in `tests/conftest.py`, because the test files stub `shared.middleware` inline\n"
                 "- Validate input at create/update time only; never reject stored data on read\n"
                 "- Anything that fetches a user-supplied URL must go through the SSRF guard in `interview_prep/handler.py`")
        t = replace_once(t, anchor, extra, "CONTRIBUTING.md")
        plan.append((p, t))

    # OpenAPI (both copies)
    for rel in ("api/openapi.yml", "api-docs/openapi.yml"):
        t, p = load(rel)
        if t is not None:
            for i, (old, new) in enumerate(OPENAPI_EDITS, 1):
                t = replace_once(t, old, new, f"{rel} edit {i}")
            plan.append((p, t))

    if errors:
        print("\nNOTHING WRITTEN. Fix these first:\n")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    for p, text in plan:
        p.write_text(text, encoding="utf-8")
        print("updated", p.relative_to(root))
    print("\nDone. Review with: git diff --stat && git diff")

if __name__ == "__main__":
    main()
