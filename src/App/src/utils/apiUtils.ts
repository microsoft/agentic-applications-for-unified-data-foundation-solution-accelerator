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
 * Get user token from localStorage
 */
export function getUserToken(): string | null {
  return localStorage.getItem("userToken");
}

/**
 * Set user token in localStorage
 */
export function setUserToken(token: string): void {
  localStorage.setItem("userToken", token);
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
