# Issues Encountered and Fixed

*Issues are numbered chronologically across the project's full history - see [CHANGELOG.md](./CHANGELOG.md) .*

Full list of issues encountered during the development of Applytic, and how each was resolved.

---

### 1. TypeScript error on CDK deploy (Partial<FunctionProps> type)

* **Issue:** runtime became optional when using Partial<FunctionProps>, causing TypeScript to reject undefined values.

* **Fix:** Added runtime explicitly to each Lambda and removed the shared defaults spread.

### 2. esbuild crash on Windows

* **Issue:** esbuild failed due to corrupted dependencies or a Node.js version mismatch.

* **Fix:** Deleted node\_modules and package-lock.json, reinstalled dependencies, and used Node 18/20 LTS.

### 3. pytest module name collision

* **Issue:** Multiple Lambda handlers were named handler.py, causing import collisions during tests.

* **Fix:** Used importlib.util.spec\_from\_file\_location() with unique module names.

### 4. Timezone-aware datetime bug in velocity calculation

* **Issue:** dateApplied was stored as a YYYY-MM-DD string and could not be subtracted from a timezone-aware datetime.

* **Fix:** Detected 10-character date strings and added UTC timezone information before subtraction.

### 5. Chat history lost on navigation

* **Issue:** Component-level useState was reset whenever the component unmounted.

* **Fix:** Lifted message state to App.tsx and passed it down as props.

### 6. GitHub Actions npm cache error

* **Issue:** cache: 'npm' requires a package-lock.json file.

* **Fix:** Removed the cache configuration and used npm install.

### 7. import.meta.env TypeScript error in CI

* **Issue:** Vite client types were not available during CI builds.

* **Fix:** Added "types": \["vite/client"] to tsconfig.json.

### 8. Bedrock model EOL

* **Issue:** The selected Bedrock model reached AWS end-of-life during development.

* **Fix:** Updated BEDROCK\_MODEL\_ID and used aws logs tail for debugging.

### 9. Bedrock inference profile requirement

* **Issue:** Claude 3.7+ models require cross-region inference profiles using a us. prefix.

* **Fix:** Updated model configuration to use the correct inference profile identifier.

### 10. IAM wildcard required for inference profiles

* **Issue:** Foundation model ARNs did not cover inference profile ARNs.

* **Fix:** Used Resource: "\*" for Bedrock IAM permissions.

### 11. AWS Marketplace subscription required

* **Issue:** Claude 3.7 and Haiku 4.5 required an AWS Marketplace subscription.

* **Fix:** Switched to Amazon Nova Lite.

### 12. Amazon Nova request/response format differences

* **Issue:** Nova models do not accept anthropic\_version in the request payload.

* **Fix:** Detected the model family from MODEL\_ID and generated the appropriate payload format.

### 13. Pie chart labels clipped

* **Issue:** External labels overflowed the chart container.

* **Fix:** Implemented a custom label renderer that draws percentage values inside slices at the midpoint radius.

### 14. Digest Lambda missing Cognito permission

* **Issue:** cognito-idp:AdminGetUser permission was missing from the IAM policy.

* **Fix:** Added an IAM policy statement targeting the Cognito User Pool ARN.

### 15. SES sandbox – recipient emails not verified

* **Issue:** New AWS accounts in the SES sandbox can only send emails to verified recipient addresses.

* **Fix:** Added a Cognito Post Confirmation trigger that automatically verifies newly registered user emails.

### 16. GitHub Pages blank page after login

* **Issue:** BrowserRouter defaulted to / while the application was hosted under /applytic/.

* **Fix:** Passed import.meta.env.BASE\_URL as the basename to BrowserRouter.

### 17. Windows pip --user + -t conflict in build\_layer.sh

* **Issue:** Windows automatically added --user, which conflicts with pip's -t option.

* **Fix:** Added the --no-user flag to the pip install command.

### 18. CDK construct ID mismatch on redeploy

* **Issue:** CloudFormation rejected deployment with a "Resource already exists" error.

* **Fix:** Preserved the original construct IDs when updating existing alarms.

### 19. Lambda ARM64 vs x86_64 architecture mismatch

* **Issue:** build\_layer.sh produced x86_64 wheels while Lambdas ran on ARM64, causing pydantic\_core runtime failures.

* **Fix:** Added --platform manylinux2014\_aarch64 --only-binary=:all: to the pip install command.

### 20. parse\_body stub missing error handling in test\_insights.py

* **Issue:** The test stub crashed on invalid JSON input.

* **Fix:** Replaced the lambda with a proper function that wraps json.loads() in a try/except block and returns HTTP 400 on failure. The stub is registered in sys.modules and reused by subsequent test files.

### 21. AddApplicationModal missing followUpDate field

* **Issue:** TypeScript builds failed after v2.0 introduced followUpDate to the Application type.

* **Fix:** Added followUpDate: null as string | null to the defaultForm object.

### 22. moto installation failure in CI

* **Issue:** The shell interpreted brackets in moto\[dynamodb,...] as glob expansion.

* **Fix:** Wrapped the package name in quotes during installation.

### 23. Vitest globals breaking tsc builds

* **Issue:** vi, beforeAll, and afterAll were not available during standard TypeScript compilation.

* **Fix:** Added "exclude": \["src/test"] to frontend/tsconfig.json.

### 24. Terms and Privacy links broken on GitHub Pages

* **Issue:** `<a href="/terms">` and `<a href="/privacy">` in `AuthModal.tsx` bypassed React Router's `basename` (`/applytic/`), navigating to `/terms` instead of `/applytic/terms` and resulting in a 404 on GitHub Pages.

* **Fix:** Replaced them with `<Link to="/terms">` and `<Link to="/privacy">`, which automatically respect the `BrowserRouter` `basename`.

### 25. followUpDate date picker missing from ApplicationDetailModal edit form

* **Issue:** followUpDate existed in the type and backend but was never rendered in the detail modal's edit mode - users had no way to set or clear a follow-up date from the UI.
* **Fix:** Added a date picker input under Job description in edit mode, wired to send null when cleared.

### 26. Notes section overwriting previous notes instead of keeping a timeline

* **Issue:** ApplicationDetailModal's notes section was a plain textarea bound to the single app.notes string field. The notes timeline Lambda and useNotes hook already existed but were never wired in, so each new note overwrote the last.
* **Fix:** Replaced the textarea with a full notes timeline UI using useNotes(app.appId) - timestamped entries, oldest first, hover-to-delete.

### 27. compute_streak using a rolling 7-day window instead of calendar weeks

* **Issue:** Streak calculation bucketed applications using `(now - applied).days // 7`, a rolling window that could split a single calendar week across two buckets depending on time of day, so the streak badge sometimes read 0 even when the weekly goal was met.
* **Fix:** Rewrote to use proper ISO week boundaries (Monday 00:00 UTC), matching what the Dashboard progress bar counts.

### 28. localhost blocked by CORS when running the frontend against the live backend

* **Issue:** `http://localhost:5173` wasn't in ALLOWED_ORIGINS in shared/middleware.py, so `npm run dev` against the deployed API failed with CORS errors.
* **Fix:** Deferred - workaround was testing directly against the deployed CloudFront/GitHub Pages URLs. CDK/middleware changes to allow localhost origins are still pending.

### 29. Unhandled promise rejections after migrating to React Query

* **Issue:** React Query's `mutateAsync` rethrows on failure by design. Two call sites (`Dashboard.tsx` goal save, `ApplicationDetailModal.tsx` add note) awaited it directly, producing console errors even though the error toast fired correctly.
* **Fix:** Wrapped both calls in try/catch with an intentionally empty catch block, since `onError` in the hook already handles the user-facing toast.

### 30. resumeVersion was free text with no link to actually-uploaded resumes

* **Issue:** Typos and inconsistent naming (`v3-ml-focused` vs `v3-ml` vs `ML v3`) silently fragmented analytics breakdowns, and would have blocked v3.0's interview-prep/rejection-pattern features which need reliable resume-version linkage.
* **Fix:** Built a `ResumeVersionSelect` dropdown sourced from `GET /resumes/list`, shared by both modals. Stale values (deleted from S3, or free-typed before this change) are preserved as a disabled, flagged option rather than dropped.

### 31. SPA hard refresh dropped `/applytic` from the URL and rendered blank

* **Issue:** `404.html` stripped `/applytic` from the path before storing it, then redirected to `/applytic/`. `index.html`'s restore script wrote that already-stripped route straight to the address bar, so a hard refresh on `hardikjp7.com/applytic/board` silently became `hardikjp7.com/board`, matching no route and rendering blank.
* **Fix:** `404.html` now stores the FULL original path verbatim; `index.html` restores it as-is - single source of truth for the base path instead of two scripts disagreeing.

### 32. Amplify Authenticator login box stuck at the top of the page

* **Issue:** Known upstream `@aws-amplify/ui-react` issue - centering styles are split across two elements, neither of which fills the viewport by default.
* **Fix:** Added a `min-height: 100vh` flex-center override scoped to `[data-amplify-authenticator]` in index.css.

### 33. `/api/docs/` returned CloudFront AccessDenied, but `/api/docs/index.html` worked

* **Issue:** CloudFront's `defaultRootObject` only applies to the distribution root, not subdirectory paths matched by `additionalBehaviors`. A request for exactly `/api/docs/` had no matching S3 object, so OAC returned 403 instead of serving the index page.
* **Fix:** Added a CloudFront Function on the `api/docs/*` behavior's viewer-request event that rewrites any URI ending in `/` to append `index.html`.

### 34. Amplify Hub event `signIn_failure` renamed in v6

* **Issue:** `AuthCallback` used `payload.event === 'signIn_failure'`, which no longer exists in Amplify v6 and caused a TypeScript error.
* **Fix:** Changed to the correct v6 event name, `signInWithRedirect_failure`.

### 35. HowItWorks connector line showed through transparent icon boxes

* **Issue:** A single absolute-positioned line spanning all four steps passed behind the semi-transparent icon boxes, making it visible through them.
* **Fix:** Replaced with individual in-flow connector divs placed between each pair of step columns, which physically cannot overlap the icon boxes.

### 36. Authenticated users saw the auth modal when clicking landing page CTAs

* **Issue:** Clicking "Get Started Free" or "Log in" always opened the AuthModal, even for already-signed-in users, producing a confusing "already signed in" error.
* **Fix:** Added a `useAuthStatus` hook that checks the Cognito session on mount; CTAs redirect straight to `/dashboard` when already authenticated.

### 37. Analytics page crashed on zero applications and stayed broken across navigation

* **Issue:** The empty-state check didn't account for the Lambda's `{"message": "..."}` shape returned for zero applications, throwing on `patterns.summary.total`. A single unkeyed ErrorBoundary around all routes then stayed in its error state for every later page until a hard refresh.
* **Fix:** Fixed the guard to check for a missing `summary` key; keyed the ErrorBoundary to `location.pathname` so navigation itself clears any future render error.

### 38. CodeQL flagged the HTML-stripping regex as bypassable

* **Issue:** `_strip_html`'s regex-based script/style stripping didn't recognize malformed-but-browser-accepted close tags like `</script foo="bar">`, meaning script content could leak into text passed to the interview-prep LLM prompt.
* **Fix:** Replaced with a stdlib `HTMLParser` subclass that tokenizes tag names structurally instead of pattern-matching, immune to attribute-injection or case-variation bypasses.

### 39. Privacy Policy and Terms pages had the same broken-link bug as AuthModal

* **Issue:** Both pages used bare `<a href="/">` for the logo and footer "back" links, bypassing React Router's basename the same way AuthModal originally did (see #24).
* **Fix:** Replaced all four instances with `<Link to="/">`.

### 40. FAQ accordion click caused whole-page lag

* **Issue:** FAQ cards shared the `.land-glass` class, which uses `backdrop-filter`. Opening one card's answer shifted every card below it on each animation frame, forcing the browser to repaint the expensive blur across all shifting siblings.
* **Fix:** Gave FAQ cards a dedicated solid-background class with no backdrop-filter, and switched the height animation from `max-height` to `grid-template-rows` for compositor-friendly performance.

### 41. Production bundle exceeded Vite's 500kB warning threshold

* **Issue:** Every route/page component was statically imported into a single chunk regardless of which route a user actually visited.
* **Fix:** Converted all route-level components to `React.lazy()` with `Suspense` boundaries, so each route downloads only its own chunk.

### 42. Secrets Manager billed a small daily cost for credentials only needed at deploy time

* **Issue:** AWS Cost Anomaly Detection flagged ~$0.013/day from the Google OAuth secret. Secrets Manager bills per-secret regardless of usage, and the values are only read once at CDK deploy time.
* **Fix:** Migrated to free-tier SSM Parameter Store SecureString parameters, resolved via an `AwsCustomResource` at deploy time (a direct SSM dynamic reference isn't supported on Cognito's identity provider resource property).

### 43. Google Search results didn't show the Applytic favicon (v3.1)

* **Issue:** The site only served `favicon.svg` with no PNG/ICO fallback, and `apple-touch-icon.png` was referenced in index.html but never actually existed. Google's Search favicon crawler has unreliable SVG support and expects a static PNG/ICO at a stable, crawlable URL.
* **Fix:** Generated a proper favicon.ico and PNG set (16 through 512px) plus a real apple-touch-icon.png matching the existing mark, and added them as fallback `<link>` tags alongside the SVG.

### 44. Returning from Privacy/Terms landed at the wrong scroll position (v3.1)

* **Issue:** The browser's native `history.scrollRestoration` tracks scroll per history entry independently of React Router, then reapplies a stale offset against freshly re-mounted content that doesn't line up - "Back to Applytic" always landed near the Features section instead of where the user had scrolled from. A first attempt using unmount-cleanup to save scroll position also failed under React 18 StrictMode's dev-only double-invoke, which cleared the saved value before it could be used.
* **Fix:** Set `scrollRestoration = 'manual'` and took full manual control - a live scroll listener persists position, restoration only fires on real back-navigation (detected via `useNavigationType`), and "Back to Applytic" now triggers genuine `navigate(-1)` instead of a fresh link navigation.

### 45. CSV import broke the TypeScript build after salary fields were added (v3.1)

* **Issue:** `KanbanBoard.tsx`'s CSV import path builds an `Application`-shaped object for `create()`. Once `expectedSalary`/`offeredSalary`/`salaryNotes` became required members of that type, the build failed with a missing-properties error.
* **Fix:** Added the three fields to the import object with fixed defaults - CSV import does not support salary columns.