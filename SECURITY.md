# Daily Yield Security Policy

## Protected systems

- Private GitHub repository and encrypted Actions secrets
- Daily Yield Blogger Pages and Posts through the authenticated Blogger API
- Publishing workflows for Articles, News and Facebook

## Automated controls

- Daily authenticated Blogger API backups are retained as private workflow artifacts for 30 days.
- Critical source/workflow hashes, existing Page/Post hashes, deletions, credential patterns and common malicious injection primitives are monitored.
- A detected anomaly fails the workflow and preserves evidence without accepting the changed baseline.
- The monitor never requests the public Daily Yield website and therefore creates no synthetic pageviews.

## Platform boundary

Blogger hosting, TLS, network filtering and server patching are operated by Google. This repository cannot install a server daemon or WAF on Blogger. GitHub Actions schedules can be delayed and are not a real-time guarantee. Account security therefore remains essential: use a passkey or security key, 2-Step Verification, recovery methods, minimum Blogger administrators and periodic Google Security Checkup.

## Layout and content rights

Daily Yield's original design, branding, graphics and editorial presentation are protected by copyright. Public browser-delivered HTML, CSS and JavaScript cannot be made technically impossible to inspect or copy. Repository privacy, provenance records, distinctive branding, dated backups and enforcement notices provide deterrence and evidence; disabling right-click or obfuscating code is not considered effective protection.

## Incident response

1. Do not approve a changed security baseline until the difference is understood.
2. Revoke suspicious Google/GitHub sessions and rotate affected tokens.
3. Disable publishing workflows if credentials may be compromised.
4. Restore affected content from a known-good security artifact or Blogger backup.
5. Review Blogger administrators, GitHub collaborators and OAuth grants.
