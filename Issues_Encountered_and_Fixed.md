\# Issues Encountered and Fixed



Full list of issues encountered during the development of Applytic, and how each was resolved.



\---



\### 1. TypeScript error on CDK deploy (`Partial<FunctionProps>` type)



\* \*\*Issue:\*\* `runtime` became optional when using `Partial<FunctionProps>`, causing TypeScript to reject undefined values.

\* \*\*Fix:\*\* Added `runtime` explicitly to each Lambda and removed the shared defaults spread.



\### 2. esbuild crash on Windows



\* \*\*Issue:\*\* esbuild failed due to corrupted dependencies or a Node.js version mismatch.

\* \*\*Fix:\*\* Deleted `node\_modules` and `package-lock.json`, reinstalled dependencies, and used Node 18/20 LTS.



\### 3. pytest module name collision



\* \*\*Issue:\*\* Multiple Lambda handlers were named `handler.py`, causing import collisions during tests.

\* \*\*Fix:\*\* Used `importlib.util.spec\_from\_file\_location()` with unique module names.



\### 4. Timezone-aware datetime bug in velocity calculation



\* \*\*Issue:\*\* `dateApplied` was stored as a `YYYY-MM-DD` string and could not be subtracted from a timezone-aware datetime.

\* \*\*Fix:\*\* Detected 10-character date strings and added UTC timezone information before subtraction.



\### 5. Chat history lost on navigation



\* \*\*Issue:\*\* Component-level `useState` was reset whenever the component unmounted.

\* \*\*Fix:\*\* Lifted message state to `App.tsx` and passed it down as props.



\### 6. GitHub Actions npm cache error



\* \*\*Issue:\*\* `cache: 'npm'` requires a `package-lock.json` file.

\* \*\*Fix:\*\* Removed the cache configuration and used `npm install`.



\### 7. `import.meta.env` TypeScript error in CI



\* \*\*Issue:\*\* Vite client types were not available during CI builds.

\* \*\*Fix:\*\* Added `"types": \["vite/client"]` to `tsconfig.json`.



\### 8. Bedrock model EOL



\* \*\*Issue:\*\* The selected Bedrock model reached AWS end-of-life during development.

\* \*\*Fix:\*\* Updated `BEDROCK\_MODEL\_ID` and used `aws logs tail` for debugging.



\### 9. Bedrock inference profile requirement



\* \*\*Issue:\*\* Claude 3.7+ models require cross-region inference profiles using a `us.` prefix.

\* \*\*Fix:\*\* Updated model configuration to use the correct inference profile identifier.



\### 10. IAM wildcard required for inference profiles



\* \*\*Issue:\*\* Foundation model ARNs did not cover inference profile ARNs.

\* \*\*Fix:\*\* Used `Resource: "\*"` for Bedrock IAM permissions.



\### 11. AWS Marketplace subscription required



\* \*\*Issue:\*\* Claude 3.7 and Haiku 4.5 required an AWS Marketplace subscription.

\* \*\*Fix:\*\* Switched to Amazon Nova Lite.



\### 12. Amazon Nova request/response format differences



\* \*\*Issue:\*\* Nova models do not accept `anthropic\_version` in the request payload.

\* \*\*Fix:\*\* Detected the model family from `MODEL\_ID` and generated the appropriate payload format.



\### 13. Pie chart labels clipped



\* \*\*Issue:\*\* External labels overflowed the chart container.

\* \*\*Fix:\*\* Implemented a custom label renderer that draws percentage values inside slices at the midpoint radius.



\### 14. Digest Lambda missing Cognito permission



\* \*\*Issue:\*\* `cognito-idp:AdminGetUser` permission was missing from the IAM policy.

\* \*\*Fix:\*\* Added an IAM policy statement targeting the Cognito User Pool ARN.



\### 15. SES sandbox – recipient emails not verified



\* \*\*Issue:\*\* New AWS accounts in the SES sandbox can only send emails to verified recipient addresses.

\* \*\*Fix:\*\* Added a Cognito Post Confirmation trigger that automatically verifies newly registered user emails.



\### 16. GitHub Pages blank page after login



\* \*\*Issue:\*\* `BrowserRouter` defaulted to `/` while the application was hosted under `/applytic/`.

\* \*\*Fix:\*\* Passed `import.meta.env.BASE\_URL` as the `basename` to `BrowserRouter`.



\### 17. Windows pip `--user` + `-t` conflict in `build\_layer.sh`



\* \*\*Issue:\*\* Windows automatically added `--user`, which conflicts with pip's `-t` option.

\* \*\*Fix:\*\* Added the `--no-user` flag to the pip install command.



\### 18. CDK construct ID mismatch on redeploy



\* \*\*Issue:\*\* CloudFormation rejected deployment with a "Resource already exists" error.

\* \*\*Fix:\*\* Preserved the original construct IDs when updating existing alarms.



\### 19. Lambda ARM64 vs x86\_64 architecture mismatch



\* \*\*Issue:\*\* `build\_layer.sh` produced x86\_64 wheels while Lambdas ran on ARM64, causing `pydantic\_core` runtime failures.

\* \*\*Fix:\*\* Added `--platform manylinux2014\_aarch64 --only-binary=:all:` to the pip install command.



\### 20. `parse\_body` stub missing error handling in `test\_insights.py`



\* \*\*Issue:\*\* The test stub crashed on invalid JSON input.

\* \*\*Fix:\*\* Replaced the lambda with a proper function that wraps `json.loads()` in a try/except block and returns HTTP 400 on failure. The stub is registered in `sys.modules` and reused by subsequent test files.



\### 21. `AddApplicationModal` missing `followUpDate` field



\* \*\*Issue:\*\* TypeScript builds failed after v2.0 introduced `followUpDate` to the `Application` type.

\* \*\*Fix:\*\* Added `followUpDate: null as string | null` to the `defaultForm` object.



\### 22. moto installation failure in CI



\* \*\*Issue:\*\* The shell interpreted brackets in `moto\[dynamodb,...]` as glob expansion.

\* \*\*Fix:\*\* Wrapped the package name in quotes during installation.



\### 23. Vitest globals breaking `tsc` builds



\* \*\*Issue:\*\* `vi`, `beforeAll`, and `afterAll` were not available during standard TypeScript compilation.

\* \*\*Fix:\*\* Added `"exclude": \["src/test"]` to `frontend/tsconfig.json`.



\### 24. Terms and Privacy links broken on GitHub Pages



\* \*\*Issue:\*\* `<a href="/terms">` and `<a href="/privacy">` in `AuthModal.tsx` bypassed React Router's basename (`/applytic/`), navigating to `/terms` instead of `/applytic/terms` and hitting a 404 on GitHub Pages.

\* \*\*Fix:\*\* Replaced with `<Link to="/terms">` and `<Link to="/privacy">` which respect the BrowserRouter basename automatically.

