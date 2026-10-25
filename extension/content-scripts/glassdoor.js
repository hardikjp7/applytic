// Applytic - Glassdoor adapter (v3.2, popup-triggered flow)
// Loaded after shared.js on job listing and job-search pages.
//
// Selectors confirmed against live Glassdoor (.co.in). If the popup shows
// "no job detected" on a real posting after a Glassdoor redesign, check
// which selectors below still resolve.

(function () {
  const TITLE_SELECTORS = ['h1[id^="jd-job-title"]', '[data-test="job-title"]'];
  const COMPANY_SELECTORS = [
    '[data-test="employer-name"]',
    '[data-test="employerName"]',
    // Confirmed live: Glassdoor's employer name has no data-test attribute
    // at all, just a CSS-module class ("EmployerProfile_employerNameHeading__bXBYr").
    // Matching on the stable prefix (ignoring the random hash suffix that
    // changes per build) survives Glassdoor's next rebuild; matching the
    // full class name would not.
    '[class*="employerNameHeading"]',
  ];

  function queryFirst(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    return null;
  }

  function textOf(el) {
    return el ? el.textContent.trim().replace(/\s+/g, ' ') : '';
  }

  // Glassdoor sometimes carries the job ID as a `jobListingId` query param
  // on search-panel views; otherwise the ID is embedded in the URL slug
  // itself, so the path alone is already unique per posting.
  function canonicalUrl() {
    const params = new URLSearchParams(window.location.search);
    const jobListingId = params.get('jobListingId');
    if (jobListingId) {
      return `${window.location.origin}${window.location.pathname}?jl=${jobListingId}`;
    }
    return `${window.location.origin}${window.location.pathname}`;
  }

  function getJobData() {
    const role = textOf(queryFirst(TITLE_SELECTORS));
    const company = textOf(queryFirst(COMPANY_SELECTORS));
    if (!role || !company) return null;

    return {
      company,
      role,
      source: 'job-board',
      jobDescUrl: canonicalUrl(),
    };
  }

  window.ApplyticContent.registerJobDataProvider(getJobData, 'glassdoor');
})();
