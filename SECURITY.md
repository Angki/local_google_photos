# Security Policy

## Supported Versions

Security updates and bug fixes are applied to the latest release on the `main` branch.

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

---

## Reporting a Vulnerability

We take the security of this local application very seriously, especially concerning the privacy of personal photo collections.

If you discover a security vulnerability:

1. **Do NOT open a public GitHub issue.**
2. Please report the vulnerability privately by opening a [GitHub Security Advisory](https://github.com/Angki/local_google_photos/security/advisories/new) or contacting the maintainer directly.
3. Include detailed steps to reproduce the issue, along with any relevant logs or environment details.
4. We will acknowledge receipt of your vulnerability report within 48 hours and provide a timeline for triage and remediation.

---

## Privacy Guarantee

This project is built on strict **local-first principles**:
- Original media files and metadata are never uploaded to any external server.
- AI vector embeddings are computed and stored entirely on your local machine.
- The `.gitignore` policy strictly excludes databases, thumbnails, and personal configuration files.
