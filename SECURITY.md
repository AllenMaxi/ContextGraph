# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report vulnerabilities by emailing:

**maxiallendee97@gmail.com**

Please include the following information in your report:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Any suggested fixes (if applicable)

## Operational Responsibility

ContextGraph is open-source software released under the MIT License and provided as-is. Operators remain responsible for deployment choices, access policies, regulatory compliance, and the data they put into the system.

See also:

- [Security and Operations](/Users/maximilianoallende/Documents/promptUltra/docs/security-operations.md)
- [MCP Chat Agent Integration](/Users/maximilianoallende/Documents/promptUltra/docs/mcp-chat-agent.md)

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
- Recalled memories should be treated as untrusted external context inside downstream LLM prompts

### Dependencies

- All dependencies are pinned to minimum versions in `pyproject.toml`
- Run `pip audit` regularly to check for known vulnerabilities
- Keep Python and all dependencies up to date
