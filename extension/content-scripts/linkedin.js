// Applytic - LinkedIn adapter (v3.2, popup-triggered flow)
// Loaded after shared.js on https://www.linkedin.com/jobs/*
//
// LinkedIn's own top-card markup uses fully hashed, build-specific CSS
// classes (e.g. "fe4f64b5 _90758c2f ...") with zero semantic meaning and no
// data-*/aria-* attributes on the title or company elements - confirmed via
// live inspection. document.title is the stable source instead: format
// "{Role} | {Company} in {Location} | LinkedIn" (location segment is
// sometimes absent). The <title> tag is SEO-load-bearing, so its format
// survives redesigns that gut the internal DOM.

(function () {
  function parseTitle() {
    // "LLM Model Developer | Accenture in India | LinkedIn" (confirmed live)
    const parts = document.title.split('|').map((p) => p.trim());
    if (parts.length < 2) return { role: '', company: '' };

    const role = parts[0];
    const companySegment = parts[1];

    // "Company in Location" - split on " in " only when surrounded by
    // spaces, so a company name containing "in" (e.g. "Intuit") doesn't
    // get mis-split.
    const inMatch = companySegment.match(/^(.*?)\s+in\s+.+$/);
    const company = (inMatch ? inMatch[1] : companySegment).trim();

    return { role, company };
  }

  // Cross-check against the company profile link when present - sidesteps
  // the "in Location" ambiguity entirely. Falls back to the title-parsed
  // value if this link isn't found.
  function companyFromProfileLink() {
    const el = document.querySelector('a[href*="/company/"]');
    return el ? el.textContent.trim() : '';
  }

  // Normalizes to /jobs/view/{id}/ - the same posting maps to the same URL
  // whether visited via search results or a direct link.
  function canonicalUrl() {
    const match = window.location.pathname.match(/\/jobs\/view\/(\d+)/);
    if (match) {
      return `${window.location.origin}/jobs/view/${match[1]}/`;
    }
    return window.location.href.split('?')[0];
  }

  function getJobData() {
    const { role, company: titleCompany } = parseTitle();
    const company = companyFromProfileLink() || titleCompany;

    if (!role || !company) return null;

    return {
      company,
      role,
      source: 'linkedin',
      jobDescUrl: canonicalUrl(),
    };
  }

  window.ApplyticContent.registerJobDataProvider(getJobData, 'linkedin');
})();
