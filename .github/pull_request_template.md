## Summary

<!-- What does this PR do? One or two sentences is fine. -->



## Type of Change

<!-- Check all that apply -->

- [ ] `feat` — New feature
- [ ] `fix` — Bug fix
- [ ] `chore` — Dependency update, tooling, or refactor with no behavior change
- [ ] `docs` — Documentation only
- [ ] `test` — New or updated tests
- [ ] `ci` — CI/CD pipeline change
- [ ] `security` — Security fix or hardening

---

## What Changed

<!-- Brief description of the key changes made. Be specific enough that a reviewer knows where to look. -->

**Lambda / Backend:**
- 

**Frontend:**
- 

**CDK / Infrastructure:**
- 

**Tests:**
- 

<!-- Delete any sections above that don't apply to this PR -->

---

## Related Issues

<!-- Link issues this closes or relates to -->

Closes #
Relates to #

---

## Testing Done

- [ ] All 48 existing tests pass (`python -m pytest tests/ -v`)
- [ ] New tests added for any new Lambda logic
- [ ] `npm run build` passes with no TypeScript errors
- [ ] Manually tested in local dev (`npm run dev`)
- [ ] Tested against deployed AWS backend (if applicable)

**Test output (paste or screenshot):**

```
# paste pytest output here
```

---

## AWS / Infrastructure Checklist

<!-- Only fill this in if CDK or IAM was changed -->

- [ ] No hardcoded account IDs, ARNs, or bucket names added
- [ ] IAM policies follow least-privilege
- [ ] `cdk diff` reviewed before deploying
- [ ] No new environment variables added without updating Lambda configuration docs

---

## Security Checklist

- [ ] No secrets, tokens, or credentials committed
- [ ] CORS origins not broadened beyond current wildcard
- [ ] No new `Resource: "*"` IAM statements unless strictly necessary (document reason below)

**Reason for broad IAM resource (if applicable):**


---

## Screenshots / Demo

<!-- For frontend changes, add a screenshot or short screen recording. For API changes, paste a sample request/response. -->



---

## Notes for Reviewer

<!-- Anything specific you want the reviewer to focus on, known limitations, or follow-up items. -->


