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
 * Create an error Response object
 */
export function createErrorResponse(status: number = 500, statusText: string = 'Internal Server Error'): Response {
  return new Response(null, {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' },
  });
}
