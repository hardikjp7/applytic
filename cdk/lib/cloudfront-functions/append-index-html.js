// CloudFront Function - appends index.html to directory-style requests.
//
// Bug fix: distribution-level `defaultRootObject: 'index.html'` only applies
// to the root `/` request. It does NOT apply to subdirectory paths matched by
// additionalBehaviors (e.g. 'api/docs/*') - so a request for exactly
// /api/docs/ (no filename) was passed to S3 verbatim, which has no object
// literally named "api/docs/" (only "api/docs/index.html" exists), and OAC
// returns AccessDenied (403) instead of a friendly 404 for missing keys.
//
// This function runs on viewer-request for the api/docs/* behavior only and
// rewrites any URI ending in '/' to '/index.html', so CloudFront requests
// the correct object key from S3.
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  }

  return request;
}
