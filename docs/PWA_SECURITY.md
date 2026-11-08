# PWA Security

The PWA is served by the FastAPI application on the same origin as `/api`. It has no configurable API host, third-party scripts, analytics, or cross-origin API access. Use it only through the Raspberry Pi's HTTPS name provided by Tailscale Serve. The backend remains bound to loopback; do not publish it with router port forwarding or Tailscale Funnel.

## Bearer Token

- The user enters the existing `SERVER_MANAGER_API_TOKEN` at sign-in.
- The token exists only in the page's JavaScript memory and request `Authorization` headers. It is not written to `localStorage`, `sessionStorage`, IndexedDB, the URL, or the service worker cache.
- Reloading/closing the page, using **Blocca**, an unauthorized response, or 15 minutes without user activity clears the in-memory token and returns to sign-in.
- API requests use same-origin mode, omit cookies/credentials, disable HTTP caching, and reject redirects. The API does not enable CORS.
- Never embed a production bearer token in the PWA bundle. A bearer token grants the holder the administrative permissions of the API; there is no per-user RBAC.

## Browser Isolation

The API sends a restrictive Content Security Policy and anti-framing/content-type headers. The service worker caches only the static PWA shell and explicitly bypasses `/api/`; offline mode cannot read or control services. Dynamic values from the API are inserted as text, not interpreted as HTML.

HTTPS is required for non-local use. The browser's local loopback exception exists for development and does not mean a remote HTTP connection is acceptable. The PWA cannot independently prove that a secure HTTPS host belongs to your tailnet: the operator must use the tailnet URL and enforce Tailscale ACLs. Avoid shared/unlocked devices, keep browsers and Android updated, and use a password manager outside the PWA to protect the token if you need to store it.

## Residual Risks

Anyone who obtains the token can perform all API operations until it is rotated. A compromised phone/computer, malicious browser extension, or same-origin code compromise can read the token while the session is active. Tailscale limits network reachability but does not replace the bearer token; the bearer token does not replace device security or tailnet ACLs. Rotate the token in the protected environment file and restart the service if a device is lost or compromise is suspected.
