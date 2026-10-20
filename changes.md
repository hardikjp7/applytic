# v3.2.1 Session 2 - Hardening edits

Branch: same `fix/v3.2.1-security-and-fixes`. Backend and CDK first, then the two small frontend edits.

Already written as full files (copy into the repo as-is):
- `lambdas/shared_layer/python/shared/pagination.py`
- `tests/test_pagination.py`

Everything else below is an edit to an existing file. Where a snippet says "replace", the old text is quoted or named so you can find it.

Verified in a scratch environment (not inside your repo): the SSRF guard and redirect logic (against a local server), the validators (real pydantic), and the pagination helper plus its tests. The handler-level test edits are written against your existing test patterns but have not been run, so run the full suite after applying.

---

## 1. SSRF guard - `lambdas/interview_prep/handler.py`

### 1a. Imports (top of file)

Replace

```python
import json
import os
import re
import uuid
from html.parser import HTMLParser
from urllib import request as urllib_request
from urllib.error import URLError
```

with

```python
import ipaddress
import json
import os
import re
import socket
import uuid
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
```

### 1b. Constants

Replace

```python
JD_MAX_CHARS = 3000
FETCH_TIMEOUT = 5  # seconds
NUM_QUESTIONS = 10
```

with

```python
JD_MAX_CHARS = 3000
FETCH_TIMEOUT = 5  # seconds
NUM_QUESTIONS = 10

# v3.2.1: SSRF guard + per-user daily cap on generate calls
MAX_REDIRECTS = 3
ALLOWED_FETCH_PORTS = {80, 443}
PREP_DAILY_LIMIT = int(os.environ.get("PREP_DAILY_LIMIT", "10"))
```

### 1c. Replace the whole `fetch_job_description` function

Delete the existing `fetch_job_description` (including its `@tracer.capture_method` decorator) and put this in its place. The guard helpers go directly above it.

```python
class UnsafeUrlError(ValueError):
    """Raised when a job description URL points somewhere we must not fetch."""


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])  # strip IPv6 scope id
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:127.0.0.1 must be judged as 127.0.0.1
    return ip.is_global and not ip.is_multicast


def _assert_public_url(url: str) -> None:
    """
    Raises UnsafeUrlError unless the URL is http(s) on port 80/443 and its
    host resolves ONLY to public addresses. Judging the resolved address (not
    the hostname text) also catches 127.1, 0x7f.1, 2130706433 and
    names that resolve to private ranges.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("scheme not allowed")
    host = parsed.hostname
    if not host or parsed.username or parsed.password:
        raise UnsafeUrlError("host missing or credentials in URL")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in ALLOWED_FETCH_PORTS:
        raise UnsafeUrlError("port not allowed")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeUrlError("host does not resolve") from e
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public_ip(a) for a in addresses):
        raise UnsafeUrlError("host resolves to a non-public address")


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    """Return None so urllib raises HTTPError on 3xx; we follow hops ourselves."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib_request.build_opener(_NoRedirectHandler)
_REDIRECT_CODES = {301, 302, 303, 307, 308}


@tracer.capture_method
def fetch_job_description(url: str) -> str:
    """
    Fetches job description text from a URL.
    Returns up to JD_MAX_CHARS of stripped text.
    Returns empty string on any failure - caller falls back gracefully.

    v3.2.1: every hop (the original URL and each redirect, max MAX_REDIRECTS)
    is checked by _assert_public_url before it is requested.
    Known limit: urllib resolves the host again when it connects, so a DNS
    rebinding attacker could still race between our check and the connect.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_public_url(current)
            req = urllib_request.Request(
                current,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Applytic/3.0)"},
            )
            try:
                with _opener.open(req, timeout=FETCH_TIMEOUT) as response:
                    raw = response.read(50_000).decode("utf-8", errors="ignore")
                return _strip_html(raw)[:JD_MAX_CHARS]
            except HTTPError as e:
                location = e.headers.get("Location") if e.code in _REDIRECT_CODES else None
                if not location:
                    raise
                current = urljoin(current, location)
        logger.warning("JD fetch stopped - too many redirects", extra={"url": url})
        return ""
    except UnsafeUrlError as e:
        logger.warning("JD fetch blocked - unsafe URL", extra={"url": url, "reason": str(e)})
        return ""
    except Exception as e:
        logger.warning("JD fetch failed - using fallback", extra={"url": url, "error": str(e)})
        return ""
```

## 2. Interview-prep rate limit - same file

### 2a. New function (put it after `verify_application_owner`)

```python
@tracer.capture_method
def check_generate_limit(user_id: str) -> tuple[bool, int]:
    """
    Daily cap on POST .../generate (each call is a Bedrock invocation).
    Same pattern as the AI Coach limiter in insights/handler.py, separate
    counter: PK=RATELIMIT#{userId}, SK=PREPGEN#{YYYY-MM-DD}, TTL 2 days.
    Fails open on error but logs at ERROR level - the chat limiter failed
    open silently for months (v3.1.1 IAM lesson), so this one must be loud.
    """
    now = datetime.now(timezone.utc)
    try:
        result = table.update_item(
            Key={"PK": f"RATELIMIT#{user_id}", "SK": f"PREPGEN#{now.strftime('%Y-%m-%d')}"},
            UpdateExpression="ADD #count :inc SET #ttl = :ttl",
            ExpressionAttributeNames={"#count": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":inc": 1,
                ":ttl": int((now + timedelta(days=2)).timestamp()),
            },
            ReturnValues="UPDATED_NEW",
        )
        count = int(result["Attributes"]["count"])
        return count <= PREP_DAILY_LIMIT, max(0, PREP_DAILY_LIMIT - count)
    except Exception:
        logger.exception("PREP RATE LIMIT CHECK FAILED - allowing request")
        return True, PREP_DAILY_LIMIT
```

### 2b. In `lambda_handler`, the generate branch

Replace

```python
            app = verify_application_owner(user_id, app_id)
            if not app:
                return resp(404, {"error": "Application not found"}, event)

            role = app.get("role", "Software Engineer")
```

(the first occurrence, inside the `/generate` branch) with

```python
            app = verify_application_owner(user_id, app_id)
            if not app:
                return resp(404, {"error": "Application not found"}, event)

            # v3.2.1: checked after the ownership test so a bad appId cannot burn quota
            allowed, _remaining = check_generate_limit(user_id)
            if not allowed:
                return resp(429, {
                    "error": f"Daily limit reached. You can generate interview questions up to {PREP_DAILY_LIMIT} times per day.",
                    "rateLimited": True,
                }, event)

            role = app.get("role", "Software Engineer")
```

### 2c. Frontend - `frontend/src/hooks/useInterviewPrep.ts`

My Session plan assumed the frontend already shows real API errors. It does not for this hook (only the useApplications fix covered that), so a 429 would show the generic toast. Replace the generate mutation's `onError`:

```ts
    onError: (err: any) =>
      toast.error(err?.response?.data?.error ?? 'Failed to generate questions'),
```

## 3. Input validation (create/update time only) - `lambdas/applications/handler.py`

Stored data is never re-validated on read, so old records still load.

### 3a. Imports

Add `import re` to the stdlib imports, and `from datetime import datetime` next to them. Also add the pagination import (used in section 5):

```python
import os
import re
import uuid
from datetime import datetime
```

and below the existing `from shared.middleware import ...` line:

```python
from shared.pagination import paginate_query
```

### 3b. Helpers (put above `class CreateApplicationRequest`)

```python
MAX_URL_LENGTH = 2048
_BAD_KEY_CHARS = re.compile(r'[/\\\x00-\x1f\x7f]')


def _validate_ymd(v: Optional[str], field: str) -> Optional[str]:
    """Blank means 'not provided' (None); anything else must be a real YYYY-MM-DD date."""
    if v is None:
        return None
    v = v.strip()
    if v == "":
        return None
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{field} must be a valid YYYY-MM-DD date")
    return v


def _validate_job_url(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if v == "":
        return ""
    if len(v) > MAX_URL_LENGTH:
        raise ValueError(f"jobDescUrl must be {MAX_URL_LENGTH} characters or less")
    if not v.lower().startswith(("http://", "https://")):
        raise ValueError("jobDescUrl must start with http:// or https://")
    return v


def _validate_s3_name(v: str, field: str, max_len: int) -> str:
    """Used for resume versionName/filename, which become S3 key segments."""
    v = v.strip()
    if not v or len(v) > max_len:
        raise ValueError(f"{field} must be 1-{max_len} characters")
    if _BAD_KEY_CHARS.search(v) or v in (".", ".."):
        raise ValueError(f"{field} must not contain slashes or control characters")
    return v
```

### 3c. `CreateApplicationRequest` - add two validators

Add inside the class (next to the existing `valid_date_format` for `followUpDate`):

```python
    @field_validator("dateApplied")
    @classmethod
    def valid_date_applied(cls, v: Optional[str]) -> Optional[str]:
        return _validate_ymd(v, "dateApplied")

    @field_validator("jobDescUrl")
    @classmethod
    def valid_job_desc_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_job_url(v)
```

A blank `dateApplied` becomes `None`, so the existing `req.dateApplied or ts[:10]` falls back to today.

### 3d. `UpdateApplicationRequest` - add the same two validators

Identical bodies. A blank `dateApplied` becomes `None`, which `model_dump(exclude_none=True)` drops, so clearing the date field in the edit form leaves the stored date unchanged instead of writing an empty string.

### 3e. `UploadUrlRequest` - replace the whole class

```python
class UploadUrlRequest(BaseModel):
    filename: str
    versionName: Optional[str] = "v1"
    contentType: Optional[str] = "application/pdf"

    @field_validator("filename")
    @classmethod
    def valid_filename(cls, v: str) -> str:
        return _validate_s3_name(v, "filename", 128)

    @field_validator("versionName")
    @classmethod
    def valid_version_name(cls, v: Optional[str]) -> str:
        return "v1" if v is None else _validate_s3_name(v, "versionName", 64)

    @field_validator("contentType")
    @classmethod
    def pdf_only(cls, v: Optional[str]) -> str:
        if v is not None and v != "application/pdf":
            raise ValueError("only application/pdf uploads are supported")
        return v or "application/pdf"
```

### 3f. Chat message cap - `lambdas/insights/handler.py`

Add a constant under `MAX_INTERVIEW_APPS_FOR_CONTEXT`:

```python
MAX_CHAT_MESSAGE_LENGTH = 1000  # v3.2.1
```

and extend the `ChatRequest` validator:

```python
    @field_validator("message")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        if len(v) > MAX_CHAT_MESSAGE_LENGTH:
            raise ValueError(f"message must be {MAX_CHAT_MESSAGE_LENGTH} characters or less")
        return v
```

Frontend - `frontend/src/components/chat/CoachChat.tsx`, add `maxLength={1000}` to the message `<input>` so users hit the limit in the box, not as a generic "something went wrong".

### Behavior changes users can notice
- A job URL typed without `http(s)://` (for example `linkedin.com/jobs/1`) is now rejected with a clear message. Editing an old record that still holds such a value will fail until the URL is fixed.
- A malformed or impossible date (such as `2024-02-30`) is rejected.
- Resume version names and filenames cannot contain `/` or `\`. Non-PDF content types are refused.
- These messages only reach the user if the toast shows the API error. `useApplications.ts` in the snapshot I have still shows generic toasts (see my Session 1 note); confirm that fix is in your repo.

## 4. Logs - mask emails, stop API Gateway logging bodies

### 4a. `lambdas/cognito_verify/handler.py` and `lambdas/digest/handler.py`

Define the same small helper locally in each file (not in `shared.middleware`, because the test stubs would not provide it):

```python
def _mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"
```

Then use it in every log call that currently passes the address.

cognito_verify - two places:

```python
logger.info("Email already SES-verified, skipping", extra={"email": _mask_email(email)})
...
logger.info("SES verification email sent", extra={
    "email": _mask_email(email),
    "trigger_source": event.get("triggerSource"),
})
```

digest - one place:

```python
logger.info("Digest sent", extra={"email": _mask_email(email), "alert_count": len(alert_messages)})
```

### 4b. API Gateway data tracing (found while reading the stack, not on the original list)

`applytic-stack.ts` has `dataTraceEnabled: true` in the stage's `deployOptions`. With data trace on, API Gateway execution logs include request and response bodies and headers, which means ID tokens and every application's notes and contact details land in CloudWatch. Section 7 sets it to `false`. Metrics, X-Ray tracing and INFO-level method logging stay on. It only reduces logging; drop that one line if you disagree.

## 5. Pagination - adopt the helper

Each file gets `from shared.pagination import paginate_query` (and `paginate_scan` where noted) below its existing `from shared.middleware import ...` line. Do not touch `fetch_recent_notes_for_app` in insights: it passes `Limit=` and must not be paginated.

**`applications/handler.py`**

```python
@tracer.capture_method
def list_applications(user_id: str):
    items = paginate_query(
        table,
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
        ScanIndexForward=False,
    )
    return items, len(items)
```

```python
@tracer.capture_method
def list_resumes(user_id: str, event: dict) -> dict:
    prefix = f"resumes/{user_id}/"
    kwargs = {"Bucket": RESUME_BUCKET, "Prefix": prefix}
    resumes = []
    while True:
        result = s3_client.list_objects_v2(**kwargs)
        for obj in result.get("Contents", []):
            key = obj["Key"]
            parts = key.replace(prefix, "").split("/")
            if len(parts) >= 2:
                resumes.append({
                    "versionName": parts[0], "filename": parts[1],
                    "uploadedAt": obj["LastModified"].strftime("%Y-%m-%d"), "s3Key": key,
                })
        if result.get("IsTruncated") is True and result.get("NextContinuationToken"):
            kwargs["ContinuationToken"] = result["NextContinuationToken"]
        else:
            break
    resumes.sort(key=lambda x: x["uploadedAt"], reverse=True)
    return resp(200, {"resumes": resumes}, event)
```

**`insights/handler.py`**

```python
@tracer.capture_method
def fetch_all_applications(user_id: str) -> list:
    items = paginate_query(
        table,
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    return [item for item in items if item.get("entityType") == "APPLICATION"]
```

**`digest/handler.py`** (import both `paginate_query` and `paginate_scan`)

```python
@tracer.capture_method
def get_active_users() -> list[dict]:
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    items = paginate_scan(
        table,
        FilterExpression=Attr("entityType").eq("APPLICATION") &
                         Attr("updatedAt").gte(one_week_ago),
        ProjectionExpression="userId, GSI1PK",
    )
    seen = set()
    users = []
    for item in items:
        uid = item.get("userId")
        if uid and uid not in seen:
            seen.add(uid)
            users.append({"userId": uid})
    return users


@tracer.capture_method
def get_user_apps(user_id: str) -> list:
    items = paginate_query(
        table,
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    return [i for i in items if i.get("entityType") == "APPLICATION"]
```

Note: `get_active_users` is a filtered full-table scan. Paginating it makes it correct (it used to read only the first 1 MB), but it reads the whole table every Monday. A sparse GSI replaces it in v4.0.

**`followup/handler.py`** (import `paginate_scan`)

```python
    return paginate_scan(
        table,
        FilterExpression=(
            Attr("entityType").eq("APPLICATION") &
            Attr("followUpDate").exists() &
            Attr("followUpDate").lte(today) &
            Attr("status").is_in(list(FOLLOWUP_STATUSES))
        ),
        ProjectionExpression="appId, userId, company, #r, followUpDate, #s, dateApplied",
        ExpressionAttributeNames={"#r": "role", "#s": "status"},
    )
```

(replacing the `result = table.scan(...)` plus `return result.get("Items", [])`).

**`settings/handler.py`**

```python
# compute_streak
    items = paginate_query(
        table,
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
    )
    apps = [i for i in items if i.get("entityType") == "APPLICATION"]

# list_alerts
    items = paginate_query(
        table,
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("ALERT#"),
        ScanIndexForward=False,  # newest first
    )

# dismiss_alert
    items = paginate_query(
        table,
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("ALERT#"),
    )
    match = next((i for i in items if i.get("alertId") == alert_id), None)
```

(each replaces its `result = table.query(...)` and the following `items = result.get("Items", ...)` / `apps = [... result.get("Items", []) ...]` lines).

**`notes/handler.py` and `contacts/handler.py`** - same two spots in each. `list_notes` / `list_contacts`:

```python
    return paginate_query(
        table,
        KeyConditionExpression=(
            Key("PK").eq(f"APP#{app_id}") &
            Key("SK").begins_with("NOTE#")     # "CONTACT#" in contacts
        ),
        FilterExpression=Attr("entityType").eq("NOTE"),   # "CONTACT" in contacts
        ScanIndexForward=True,  # oldest first
    )
```

and in `delete_note` / `delete_contact` replace the query with `items = paginate_query(table, KeyConditionExpression=..., FilterExpression=...)` (the delete lookup filters after reading, so a note beyond the first page was previously "not found").

### 5b. `tests/conftest.py`

Test files stub `shared.middleware` inline, which would make every handler fail at `from shared.pagination import ...`. Register the real module once, at the top of `conftest.py` (after the existing `os.environ.setdefault` lines):

```python
import importlib.util
import sys

_pag_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'lambdas', 'shared_layer', 'python', 'shared', 'pagination.py'
))
_pag_spec = importlib.util.spec_from_file_location('shared.pagination', _pag_path)
_pag_mod = importlib.util.module_from_spec(_pag_spec)
_pag_spec.loader.exec_module(_pag_mod)
sys.modules['shared.pagination'] = _pag_mod
```

Existing mocks return plain dicts with no `LastEvaluatedKey`, so every paginated call finishes in one pass and the existing `assert_called_once()` checks still hold.

## 6. Test edits

### 6a. `tests/test_interview_prep.py`

Add to the helper assignments near the top:

```python
check_generate_limit = _mod.check_generate_limit
PREP_DAILY_LIMIT = _mod.PREP_DAILY_LIMIT
```

and `from urllib.error import HTTPError` to the imports.

**Replace the whole `TestFetchJobDescription` class.** The old tests patched `urllib_request.urlopen`, which the new code no longer calls, and would otherwise do real DNS lookups for example.com.

```python
def _fake_response(html: str):
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = html.encode()
    return resp


class TestFetchJobDescription:

    def test_returns_empty_for_empty_url(self):
        assert fetch_job_description("") == ""

    def test_returns_empty_for_non_http_url(self):
        assert fetch_job_description("ftp://example.com") == ""

    def test_returns_empty_on_network_error(self):
        with patch("interview_prep_handler._assert_public_url"), \
             patch("interview_prep_handler._opener") as opener:
            opener.open.side_effect = Exception("network error")
            assert fetch_job_description("https://example.com/job") == ""

    def test_truncates_to_jd_max_chars(self):
        with patch("interview_prep_handler._assert_public_url"), \
             patch("interview_prep_handler._opener") as opener:
            opener.open.return_value = _fake_response("<p>" + "x" * 10000 + "</p>")
            result = fetch_job_description("https://example.com/job")
        assert len(result) <= _mod.JD_MAX_CHARS

    def test_strips_html_from_fetched_content(self):
        html = "<html><body><h1>Software Engineer</h1><p>We are hiring.</p></body></html>"
        with patch("interview_prep_handler._assert_public_url"), \
             patch("interview_prep_handler._opener") as opener:
            opener.open.return_value = _fake_response(html)
            result = fetch_job_description("https://example.com/job")
        assert "<h1>" not in result
        assert "Software Engineer" in result


class TestAssertPublicUrl:

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://10.0.0.5/",
        "http://2130706433/",          # decimal form of 127.0.0.1
        "ftp://8.8.8.8/",
        "http://8.8.8.8:8080/",        # port not 80/443
        "http://user:pw@8.8.8.8/",     # credentials in URL
    ])
    def test_blocks_unsafe_urls(self, url):
        with pytest.raises(_mod.UnsafeUrlError):
            _mod._assert_public_url(url)

    def test_allows_public_ip_literal(self):
        _mod._assert_public_url("https://8.8.8.8/job")  # does not raise

    def test_blocks_hostname_that_resolves_to_private_address(self):
        fake = [(2, 1, 6, "", ("10.0.0.7", 443))]
        with patch("interview_prep_handler.socket.getaddrinfo", return_value=fake):
            with pytest.raises(_mod.UnsafeUrlError):
                _mod._assert_public_url("https://internal.example.com/job")

    def test_blocks_when_any_resolved_address_is_private(self):
        fake = [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("10.0.0.7", 443))]
        with patch("interview_prep_handler.socket.getaddrinfo", return_value=fake):
            with pytest.raises(_mod.UnsafeUrlError):
                _mod._assert_public_url("https://mixed.example.com/job")

    def test_blocks_unresolvable_host(self):
        import socket as _socket
        with patch("interview_prep_handler.socket.getaddrinfo", side_effect=_socket.gaierror):
            with pytest.raises(_mod.UnsafeUrlError):
                _mod._assert_public_url("https://nope.invalid/job")


class TestFetchRedirects:

    @staticmethod
    def _redirect(location: str):
        return HTTPError("https://example.com/a", 302, "Found", {"Location": location}, None)

    def test_follows_redirect_and_checks_every_hop(self):
        with patch("interview_prep_handler._assert_public_url") as guard, \
             patch("interview_prep_handler._opener") as opener:
            opener.open.side_effect = [self._redirect("/b"), _fake_response("hello world")]
            result = fetch_job_description("https://example.com/a")
        assert "hello world" in result
        assert guard.call_count == 2
        assert guard.call_args_list[1][0][0] == "https://example.com/b"

    def test_redirect_to_unsafe_target_returns_empty_without_requesting_it(self):
        def guard(url):
            if "169.254" in url:
                raise _mod.UnsafeUrlError("blocked")

        with patch("interview_prep_handler._assert_public_url", side_effect=guard), \
             patch("interview_prep_handler._opener") as opener:
            opener.open.side_effect = [self._redirect("http://169.254.169.254/latest")]
            assert fetch_job_description("https://example.com/a") == ""
        assert opener.open.call_count == 1

    def test_gives_up_after_max_redirects(self):
        with patch("interview_prep_handler._assert_public_url"), \
             patch("interview_prep_handler._opener") as opener:
            opener.open.side_effect = lambda *a, **k: (_ for _ in ()).throw(self._redirect("/again"))
            assert fetch_job_description("https://example.com/a") == ""
        assert opener.open.call_count == _mod.MAX_REDIRECTS + 1
```

**Add a limiter class:**

```python
class TestCheckGenerateLimit:

    def test_first_call_is_allowed(self):
        mock_table = MagicMock()
        mock_table.update_item.return_value = {"Attributes": {"count": 1}}
        with patch("interview_prep_handler.table", mock_table):
            allowed, remaining = check_generate_limit(USER_ID)
        assert allowed is True
        assert remaining == PREP_DAILY_LIMIT - 1

    def test_blocks_once_limit_exceeded(self):
        mock_table = MagicMock()
        mock_table.update_item.return_value = {"Attributes": {"count": PREP_DAILY_LIMIT + 1}}
        with patch("interview_prep_handler.table", mock_table):
            allowed, remaining = check_generate_limit(USER_ID)
        assert allowed is False
        assert remaining == 0

    def test_uses_its_own_counter_key(self):
        mock_table = MagicMock()
        mock_table.update_item.return_value = {"Attributes": {"count": 1}}
        with patch("interview_prep_handler.table", mock_table):
            check_generate_limit(USER_ID)
        key = mock_table.update_item.call_args[1]["Key"]
        assert key["PK"] == f"RATELIMIT#{USER_ID}"
        assert key["SK"].startswith("PREPGEN#")

    def test_fails_open_on_dynamodb_error(self):
        mock_table = MagicMock()
        mock_table.update_item.side_effect = Exception("AccessDenied")
        with patch("interview_prep_handler.table", mock_table):
            allowed, _ = check_generate_limit(USER_ID)
        assert allowed is True
```

**In `TestInterviewPrepLambdaHandler`:** the existing `test_generate_returns_201_on_success` now reaches the limiter. Add one more patch to its `with` block, otherwise it will attempt a real DynamoDB call:

```python
             patch("interview_prep_handler.check_generate_limit", return_value=(True, 9)), \
```

and add:

```python
    def test_generate_returns_429_when_daily_limit_reached(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=make_app_item()), \
             patch("interview_prep_handler.check_generate_limit", return_value=(False, 0)), \
             patch("interview_prep_handler.generate_questions_with_bedrock") as gen:
            result = lambda_handler(make_event("POST", f"/applications/{APP_ID}/interview-prep/generate"), None)
        assert result["statusCode"] == 429
        assert json.loads(result["body"])["rateLimited"] is True
        gen.assert_not_called()

    def test_generate_does_not_consume_quota_for_unknown_app(self):
        with patch("interview_prep_handler.verify_application_owner", return_value=None), \
             patch("interview_prep_handler.check_generate_limit") as limit:
            result = lambda_handler(make_event("POST", f"/applications/{APP_ID}/interview-prep/generate"), None)
        assert result["statusCode"] == 404
        limit.assert_not_called()
```

### 6b. `tests/test_applications.py` - new class

```python
class TestInputValidationV321:

    def _create(self, **extra):
        body = {'company': 'Stripe', 'role': 'Eng', 'status': 'applied', **extra}
        with patch('applications_handler.table') as mt:
            mt.put_item.return_value = {}
            return lambda_handler(make_event('POST', '/applications', body=body), None)

    def test_impossible_date_applied_returns_400(self):
        assert self._create(dateApplied='2024-02-30')['statusCode'] == 400

    def test_malformed_date_applied_returns_400(self):
        assert self._create(dateApplied='15/01/2024')['statusCode'] == 400

    def test_blank_date_applied_falls_back_to_today(self):
        result = self._create(dateApplied='')
        assert result['statusCode'] == 201
        assert json.loads(result['body'])['application']['dateApplied'] == '2024-01-01'

    def test_job_url_without_scheme_returns_400(self):
        assert self._create(jobDescUrl='linkedin.com/jobs/1')['statusCode'] == 400

    def test_job_url_over_2048_chars_returns_400(self):
        assert self._create(jobDescUrl='https://x.com/' + 'a' * 2100)['statusCode'] == 400

    def test_valid_job_url_is_accepted(self):
        assert self._create(jobDescUrl='https://stripe.com/jobs/123')['statusCode'] == 201

    def test_update_with_invalid_job_url_returns_400(self):
        event = make_event('PUT', '/applications/app-123',
                           path_params={'appId': 'app-123'}, body={'jobDescUrl': 'not-a-url'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_update_with_invalid_date_returns_400(self):
        event = make_event('PUT', '/applications/app-123',
                           path_params={'appId': 'app-123'}, body={'dateApplied': '2024-13-01'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_upload_url_rejects_slash_in_version_name(self):
        event = make_event('POST', '/resumes/upload-url',
                           body={'filename': 'resume.pdf', 'versionName': 'v1/evil'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_upload_url_rejects_path_in_filename(self):
        event = make_event('POST', '/resumes/upload-url',
                           body={'filename': '../resume.pdf', 'versionName': 'v1'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_upload_url_rejects_non_pdf_content_type(self):
        event = make_event('POST', '/resumes/upload-url',
                           body={'filename': 'a.pdf', 'versionName': 'v1', 'contentType': 'text/html'})
        assert lambda_handler(event, None)['statusCode'] == 400

    def test_upload_url_accepts_spaces_and_parentheses(self):
        event = make_event('POST', '/resumes/upload-url',
                           body={'filename': 'My Resume (final).pdf', 'versionName': 'Senior Backend v2'})
        with patch('applications_handler.s3_client') as ms3:
            ms3.generate_presigned_url.return_value = 'https://s3.amazonaws.com/fake-url'
            assert lambda_handler(event, None)['statusCode'] == 200
```

### 6c. `tests/test_insights.py`

```python
class TestChatRequestLimit:

    def test_message_over_limit_is_rejected(self):
        with pytest.raises(Exception):
            _mod.ChatRequest(message="x" * (_mod.MAX_CHAT_MESSAGE_LENGTH + 1))

    def test_message_at_limit_is_accepted(self):
        req = _mod.ChatRequest(message="x" * _mod.MAX_CHAT_MESSAGE_LENGTH)
        assert len(req.message) == _mod.MAX_CHAT_MESSAGE_LENGTH
```

### 6d. Email masking - `tests/test_cognito_verify.py` and `tests/test_digest.py`

```python
class TestMaskEmail:

    def test_masks_local_part(self):
        assert _mod._mask_email("hardik@example.com") == "h***@example.com"

    def test_handles_empty_and_malformed(self):
        assert _mod._mask_email("") == "***"
        assert _mod._mask_email("not-an-email") == "***"
```

## 7. CDK - `cdk/lib/applytic-stack.ts`

### 7a. Import (with the other `aws-cdk-lib/...` imports)

```ts
import * as budgets from 'aws-cdk-lib/aws-budgets';
```

### 7b. Resume bucket CORS: no wildcard

The CloudFront domain is defined after the resume bucket, so the rule has to be added afterwards.

Delete this line from the `ResumeBucket` props:

```ts
      cors: [{ allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET], allowedOrigins: ['*'], allowedHeaders: ['*'], maxAge: 3000 }],
```

and add this right after the `customDomainApplytic` constant:

```ts
    // v3.2.1: resume bucket CORS limited to the app's own origins (was '*').
    // Browser PUTs go straight to S3 via presigned URLs from these origins.
    resumeBucket.addCorsRule({
      allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET],
      allowedOrigins: [cloudfrontDomain, 'https://hardikjp7.github.io', customDomain, 'http://localhost:5173'],
      allowedHeaders: ['*'],
      maxAge: 3000,
    });
```

The extension never uploads to S3, so its origin is not needed here.

### 7c. API Gateway: throttling and data tracing

In `deployOptions`:

```ts
      deployOptions: {
        stageName: 'v1',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: false,   // v3.2.1: was true - logged request/response bodies and Authorization headers
        metricsEnabled: true,
        tracingEnabled: true,
        // v3.2.1: stage-wide defaults, applied per method. Starting values;
        // the dashboard loads several routes in parallel, so keep burst well above rate.
        throttlingRateLimit: 20,
        throttlingBurstLimit: 40,
      },
```

### 7d. Interview prep limit env var

On `InterviewPrepLambda`:

```ts
      environment: { ...commonEnv, PREP_DAILY_LIMIT: '10' },
```

(the lambda already has `table.grantReadWriteData`, which the limiter's `update_item` needs).

### 7e. Monthly budget

Reuse one email constant. Change the existing subscription line to use it, then add the budget below it.

```ts
    const alertEmail = 'hardikjparmar7@gmail.com';
    alarmTopic.addSubscription(new snsSubscriptions.EmailSubscription(alertEmail));

    // v3.2.1: monthly cost guardrail. AWS Budgets, not a billing CloudWatch
    // alarm - it does not depend on the account's "receive billing alerts"
    // preference. Covers the whole AWS account, not just this stack.
    new budgets.CfnBudget(this, 'MonthlyCostBudget', {
      budget: {
        budgetName: 'applytic-monthly-cost',
        budgetType: 'COST',
        timeUnit: 'MONTHLY',
        budgetLimit: { amount: 20, unit: 'USD' },
      },
      notificationsWithSubscribers: [
        {
          notification: {
            notificationType: 'ACTUAL',
            comparisonOperator: 'GREATER_THAN',
            threshold: 80,
            thresholdType: 'PERCENTAGE',
          },
          subscribers: [{ subscriptionType: 'EMAIL', address: alertEmail }],
        },
        {
          notification: {
            notificationType: 'FORECASTED',
            comparisonOperator: 'GREATER_THAN',
            threshold: 100,
            thresholdType: 'PERCENTAGE',
          },
          subscribers: [{ subscriptionType: 'EMAIL', address: alertEmail }],
        },
      ],
    });
```

IAM check for CI: if `cdk deploy` fails with an AccessDenied mentioning `budgets:`, add `"budgets:*"` to the `Action` list in `scripts/setup_oidc_v11.sh` and re-run the `put-role-policy` step. It may not be needed if CDK deploys through its bootstrap roles. It is harmless to add either way.

## 8. CI and docs

### 8a. API docs single source - `.github/workflows/deploy.yml`

Replace the step:

```yaml
      - name: Deploy API docs to S3
        run: aws s3 sync api-docs/ s3://${{ env.FRONTEND_BUCKET }}/api/docs/ --delete
```

with

```yaml
      - name: Deploy API docs to S3
        run: |
          cp api/openapi.yml api-docs/openapi.yml
          aws s3 sync api-docs/ s3://${{ env.FRONTEND_BUCKET }}/api/docs/ --delete
```

Then:

```bash
git rm api-docs/openapi.yml
echo "api-docs/openapi.yml" >> .gitignore
```

To preview the docs locally, `cp api/openapi.yml api-docs/` before opening `api-docs/index.html` from a local server.

### 8b. Remove hardcoded test counts

| File | Old | New |
|---|---|---|
| README.md | `\| Backend test suite \| 419 tests, 70% coverage threshold (93.2% actual) \|` | `\| Backend test suite \| pytest + moto, 70% coverage threshold enforced in CI \|` |
| README.md | `\| Frontend test suite \| 34 Vitest tests \|` | `\| Frontend test suite \| Vitest + React Testing Library \|` |
| README.md | `# 419 pytest tests (93.2% coverage)` | `# pytest unit + moto integration tests` |
| README.md | `test (pytest 410 tests, 70% coverage threshold)` | `test (pytest, 70% coverage threshold)` |
| README.md | `test-frontend (vitest 31 tests)` | `test-frontend (vitest)` |
| CONTRIBUTING.md | `# Run all 355 tests` | `# Run the full suite` |
| CONTRIBUTING.md | `**All 355 tests must pass before opening a PR.**` | `**The full suite must pass before opening a PR.**` |
| CONTRIBUTING.md | `Ensure all 355 tests pass locally` | `Ensure the full test suite passes locally` |
| .github/pull_request_template.md | `All 355 existing tests pass` | `All existing tests pass` |

Catch any leftovers with:

```bash
grep -rnE "[0-9]{2,3} (backend |pytest |Vitest |vitest |frontend )?tests" README.md CONTRIBUTING.md .github/
```

CHANGELOG entries and the knowledge file keep their historical numbers. They describe a past release.

### 8c. Terms - `frontend/src/pages/Terms.tsx`

Optional one-liner under "The service", since interview prep is now capped too:

```tsx
          <p>
            Interview question generation is limited to 10 generations per user per day, also
            resetting at midnight UTC.
          </p>
```

---

## Verification

```bash
python -m pytest tests/ -v --tb=short --cov=lambdas --cov-fail-under=70
cd frontend && npm run test && npm run build
cd cdk && cdk diff
```

`cdk diff` should show only: resume bucket CORS, API Gateway stage settings, interview-prep Lambda env var, the Budget, a changed layer version (pagination.py), and the Lambda code assets.

### Pending verification (after `cdk deploy`)
- Resume upload works from production and from `http://localhost:5173`.
- The extension still adds a job (CORS origin unaffected).
- The 11th interview-prep generation in a day returns 429 with the clear message.
- A job URL of `http://127.0.0.1/` or `http://169.254.169.254/` gives generic questions (check the CloudWatch log line "JD fetch blocked - unsafe URL").
- Normal browsing and a 50-row CSV import are not throttled.
- CloudWatch: no AccessDenied or error spikes for 24h, and no more Authorization headers or bodies in the API Gateway execution log group.
- Budget exists in the console with both notifications (AWS Budgets email subscribers do not need a confirmation click, unlike SNS).

### Suggested commits
- `feat(lambda): add pagination helper and adopt it across handlers`
- `fix(lambda): block private and redirected addresses when fetching job descriptions`
- `feat(lambda): rate limit interview prep generation per user per day`
- `fix(lambda): validate dates, job URLs, resume names and chat message length`
- `fix(lambda): mask emails in logs`
- `chore(cdk): restrict resume bucket CORS, add API throttling and monthly budget`
- `chore(ci): copy openapi spec into api-docs at deploy time`
- `docs: remove hardcoded test counts`