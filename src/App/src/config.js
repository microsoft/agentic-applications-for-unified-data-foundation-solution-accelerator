// Helper to safely read runtime config
function getRuntimeConfigValue(runtimeKey, envKey, defaultValue) {
  return (
    window._env_?.[runtimeKey] || // runtime-config.js
    process.env[envKey] ||        // .env fallback
    defaultValue                  // default fallback
  );
}

// Export a function to get API base URL at runtime
export function getApiBaseUrl() {
  return getRuntimeConfigValue("APP_API_BASE_URL", "REACT_APP_API_BASE_URL", "http://127.0.0.1:8000");
}

// Export a function to get chat landing text at runtime
export function getChatLandingText() {
  return getRuntimeConfigValue(
    "CHAT_LANDING_TEXT",
    "REACT_APP_CHAT_LANDING_TEXT",
    "You can ask questions around sales, products and orders."
  );
}