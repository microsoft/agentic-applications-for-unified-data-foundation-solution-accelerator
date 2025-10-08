# Use the official .NET 8 runtime as the base image
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime

# Install system dependencies required for SQL Server connectivity and runtime
RUN apk add --no-cache \
    curl \
    unixodbc \
    unixodbc-dev \
    libgcc \
    libstdc++ \
    icu-libs \
    krb5-libs \
    libssl3 \
    libcrypto3 \
    zlib

# Download and install Microsoft ODBC Driver 18 for SQL Server
RUN curl -O https://download.microsoft.com/download/fae28b9a-d880-42fd-9b98-d779f0fdd77f/msodbcsql18_18.5.1.1-1_amd64.apk \
    && apk add --allow-untrusted msodbcsql18_18.5.1.1-1_amd64.apk \
    && rm msodbcsql18_18.5.1.1-1_amd64.apk

# Set the working directory inside the container
WORKDIR /app

# Use multi-stage build for optimization
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build

# Set the working directory for build
WORKDIR /src

# Copy the project file first to leverage Docker layer caching
COPY CsApi.csproj ./

# Restore NuGet packages
RUN dotnet restore "CsApi.csproj"

# Copy the rest of the application code
COPY . .

# Build the application in Release mode
RUN dotnet build "CsApi.csproj" -c Release -o /app/build

# Publish the application
FROM build AS publish
RUN dotnet publish "CsApi.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Final stage: Copy the published app to the runtime image
FROM runtime AS final
WORKDIR /app

# Copy the published application from the build stage
COPY --from=publish /app/publish .

# Create a non-root user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -G appgroup -u 1001
USER appuser

# Expose port 80 for incoming traffic
EXPOSE 80

# Set environment variables for ASP.NET Core
ENV ASPNETCORE_URLS=http://+:80
ENV ASPNETCORE_ENVIRONMENT=Production

# Start the application
ENTRYPOINT ["dotnet", "CsApi.dll"]