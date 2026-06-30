# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:10.0-preview-alpine AS runtime

# Install essential dependencies and ODBC driver
RUN apk add --no-cache curl unixodbc libgcc libstdc++ icu-libs krb5-libs && \
    curl -O https://download.microsoft.com/download/fae28b9a-d880-42fd-9b98-d779f0fdd77f/msodbcsql18_18.5.1.1-1_amd64.apk && \
    apk add --allow-untrusted msodbcsql18_18.5.1.1-1_amd64.apk && \
    rm msodbcsql18_18.5.1.1-1_amd64.apk

WORKDIR /app

# Build stage
FROM mcr.microsoft.com/dotnet/sdk:10.0-preview-alpine AS build
WORKDIR /src
COPY CsApi.csproj ./
RUN dotnet restore "CsApi.csproj"
COPY . .
RUN dotnet publish "CsApi.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Final stage
FROM runtime AS final
RUN addgroup -g 1001 -S appgroup && adduser -S appuser -G appgroup -u 1001
COPY --from=build --chown=1001:1001 /app/publish /app/
USER appuser
EXPOSE 80
ENV ASPNETCORE_URLS=http://+:80 \
    ASPNETCORE_ENVIRONMENT=Production \
    DOTNET_EnableDiagnostics=0 \
    WEBSITES_PORTS=80 \
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -f http://localhost:80/health || exit 1
ENTRYPOINT ["dotnet", "CsApi.dll"]