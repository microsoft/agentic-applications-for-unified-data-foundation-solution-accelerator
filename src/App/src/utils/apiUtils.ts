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
 * Get headers with user ID
 */
export function getUserHeaders(): HeadersInit {
  const userId = getUserId();
  return {
    "Content-Type": "application/json",
    ...(userId && { "X-Ms-Client-Principal-Id": userId }),
  };
}

/**
 * Build API URL with base URL
 */
export function buildApiUrl(baseUrl: string, endpoint: string): string {
  const cleanBase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${cleanBase}${cleanEndpoint}`;
}

/**
 * Build URL with query parameters
 */
export function buildUrlWithParams(
  url: string,
  params: Record<string, string | number | boolean>
): string {
  const queryString = Object.entries(params)
    .filter(([_, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&');

  return queryString ? `${url}?${queryString}` : url;
}

/**
 * Parse JSON safely with error handling
 */
export async function safeJsonParse<T = any>(response: Response): Promise<T | null> {
  try {
    return await response.json();
  } catch (error) {
    console.error('Failed to parse JSON response:', error);
    return null;
  }
}

/**
 * Create error response
 */
export function createErrorResponse(status: number = 500, statusText: string = 'Internal Server Error'): Response {
  return new Response(null, {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * Check if response is successful
 */
export function isSuccessResponse(response: Response): boolean {
  return response.ok && response.status >= 200 && response.status < 300;
}

/**
 * Retry failed requests with exponential backoff
 */
export async function retryRequest<T>(
  requestFn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await requestFn();
    } catch (error) {
      lastError = error as Error;
      
      // Don't retry on abort
      if (error instanceof Error && error.name === 'AbortError') {
        throw error;
      }

      // Don't retry on last attempt
      if (attempt === maxRetries - 1) {
        break;
      }

      // Exponential backoff
      const delay = baseDelay * Math.pow(2, attempt);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error('Request failed after retries');
}

/**
 * Request deduplication cache
 */
class RequestCache {
  private cache: Map<string, Promise<any>> = new Map();
  private timeouts: Map<string, NodeJS.Timeout> = new Map();

  /**
   * Get or execute request
   */
  async getOrFetch<T>(
    key: string,
    fetchFn: () => Promise<T>,
    ttl: number = 5000
  ): Promise<T> {
    // Return cached promise if exists
    if (this.cache.has(key)) {
      return this.cache.get(key);
    }

    // Execute and cache the promise
    const promise = fetchFn();
    this.cache.set(key, promise);

    // Clear cache after TTL
    const timeout = setTimeout(() => {
      this.cache.delete(key);
      this.timeouts.delete(key);
    }, ttl);
    
    this.timeouts.set(key, timeout);

    try {
      const result = await promise;
      return result;
    } catch (error) {
      // Remove failed request from cache immediately
      this.cache.delete(key);
      const timeout = this.timeouts.get(key);
      if (timeout) {
        clearTimeout(timeout);
        this.timeouts.delete(key);
      }
      throw error;
    }
  }

  /**
   * Clear specific cache entry
   */
  clear(key: string): void {
    this.cache.delete(key);
    const timeout = this.timeouts.get(key);
    if (timeout) {
      clearTimeout(timeout);
      this.timeouts.delete(key);
    }
  }

  /**
   * Clear all cache
   */
  clearAll(): void {
    this.cache.clear();
    this.timeouts.forEach(timeout => clearTimeout(timeout));
    this.timeouts.clear();
  }
}

// Export singleton cache instance
export const requestCache = new RequestCache();

/**
 * Debounce function for API calls
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null;
      func(...args);
    };

    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function for API calls
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle: boolean = false;

  return function executedFunction(...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
}
