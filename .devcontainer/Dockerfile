FROM mcr.microsoft.com/devcontainers/python:3.11-bullseye

# Remove Yarn repository to avoid GPG key expiration issue
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Install PowerShell for OBO authentication setup in Codespaces / VS Code Web
RUN apt-get update \
    && apt-get install -y --no-install-recommends wget gpg apt-transport-https software-properties-common \
    && wget -q https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends powershell \
    && rm -f /tmp/packages-microsoft-prod.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*