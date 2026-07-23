## Security Guidelines

This solution uses [Managed Identity](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview) for secure access to Azure resources during local development and production deployment, eliminating the need for hard-coded credentials.

To maintain strong security practices, it is recommended that GitHub repositories built on this solution enable [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) to detect accidental secret exposure.

**Additional security considerations:**
- Enable [Microsoft Defender for Cloud](https://learn.microsoft.com/en-us/azure/defender-for-cloud) to monitor and secure Azure resources.
- Use [Virtual Networks](https://learn.microsoft.com/en-us/azure/container-apps/networking?tabs=workload-profiles-env%2Cazure-cli) or [firewall rules](https://learn.microsoft.com/en-us/azure/container-apps/waf-app-gateway) to protect Azure Container Apps from unauthorized access.

