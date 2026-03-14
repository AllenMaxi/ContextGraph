# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report vulnerabilities by emailing:

**security@contextgraph.dev**

Please include the following information in your report:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Any suggested fixes (if applicable)

## Response Timeline

- **Acknowledgement**: Within 48 hours of receiving your report
- **Initial assessment**: Within 5 business days
- **Resolution target**: Within 30 days for critical issues, 90 days for non-critical

You will receive updates at each stage. If the vulnerability is accepted, we will:

1. Develop and test a fix
2. Prepare a security advisory
3. Release the fix and publish the advisory simultaneously

If the vulnerability is declined, we will provide a detailed explanation.

## Security Considerations

### API Keys and Secrets

- Never commit `.env` files or API keys to the repository
- Use environment variables for all sensitive configuration
- Federation keys should be rotated periodically

### Network Security

- Deploy the ContextGraph server behind a reverse proxy with TLS
- Restrict federation endpoints to trusted peers using network policies or authentication
- The A2A protocol endpoints should be protected with bearer token authentication

### Data Privacy

- Claims marked as `private` are only accessible to the owning agent
- Published claims are available to federation peers; review visibility settings carefully
- Access control lists should be configured to limit claim visibility appropriately

### Dependencies

- All dependencies are pinned to minimum versions in `pyproject.toml`
- Run `pip audit` regularly to check for known vulnerabilities
- Keep Python and all dependencies up to date
