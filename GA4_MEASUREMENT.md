# GA4 measurement · 2026-10-21T09:06:43+00:00

Status: **TOKEN_REFUSED**

- analytics tag observed on the live site: **yes** (G-WLEEYTKV12)
- property: **not resolved** (unknown)
- what the stored token is permitted to do: `analytics.readonly`
- google said: `HTTP 400 The value for the 'filter' field was empty, but must be provided.`

What to do: Google refused the stored refresh token: it was made while the OAuth app was in Testing (Google expires those after 7 days), or it was revoked. Repeat the browser steps in GA4_CONNECT.md and replace only the GA4_REFRESH_TOKEN secret

This job reads Google's numbers and the public homepage only. It changes nothing on the blog, so it does not touch the publisher review.
