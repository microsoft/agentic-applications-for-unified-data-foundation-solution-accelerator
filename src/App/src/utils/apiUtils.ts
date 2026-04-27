/**
 * API Utility Functions
 * Common utilities for API requests
 */

/**
 * Get user ID from localStorage
 */
export function getUserId(): string | null {
  return localStorage.getItem("userId");
}

/**
 * Set user ID in localStorage
 */
export function setUserId(userId: string): void {
  localStorage.setItem("userId", userId);
}

/**
 * Get access token from sessionStorage (for OBO flow)
 */
export function getAccessToken(): string | null {
  return sessionStorage.getItem("accessToken");
}

/**
 * Set access token in sessionStorage (for OBO flow)
 */
export function setAccessToken(token: string): void {
  sessionStorage.setItem("accessToken", token);
}

/**
 * Create an error Response object
 */
export function createErrorResponse(status: number = 500, statusText: string = 'Internal Server Error'): Response {
  return new Response(null, {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' },
  });
}
