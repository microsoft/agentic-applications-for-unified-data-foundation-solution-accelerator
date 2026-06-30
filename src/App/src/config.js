function getRuntimeConfigValue(runtimeKey, envKey, defaultValue) {
   if (typeof window !== "undefined" && window._env_?.[runtimeKey]) {
    const val = window._env_[runtimeKey].trim();
    if (val && val !== `$${runtimeKey}`) {
      return val;
    }   
  }
  if (process.env[envKey]) {
    return process.env[envKey];
  }  
  return defaultValue;
}
export function getApiBaseUrl() {
  return getRuntimeConfigValue("APP_API_BASE_URL", "REACT_APP_API_BASE_URL", "http://127.0.0.1:8000");
}
export function getChatLandingText() {
  return getRuntimeConfigValue(
    "CHAT_LANDING_TEXT",
    "REACT_APP_CHAT_LANDING_TEXT",
    "You can ask questions around sales, products and orders."
  );
}

export function isWorkShopDeployment() {
  const rawValue = getRuntimeConfigValue(
    "IS_WORKSHOP",
    "REACT_APP_IS_WORKSHOP",
    "false"
  );
  // Strip quotes and whitespace that might be included
  const value = rawValue.replace(/['"]/g, '').trim().toLowerCase();
  return value === "true";
}

export function getAppTitlePrimary() {
  return getRuntimeConfigValue(
    "APP_TITLE_PRIMARY",
    "REACT_APP_APP_TITLE_PRIMARY",
    "Contoso"
  );
}

export function getAppTitleSecondary() {
  return getRuntimeConfigValue(
    "APP_TITLE_SECONDARY",
    "REACT_APP_APP_TITLE_SECONDARY",
    "| Unified Data Analysis Agents"
  );
}