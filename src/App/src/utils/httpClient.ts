/**
 * HTTP Client Utility
 * Centralized HTTP client with error handling, interceptors, and request configuration
 */

import { ApiErrorHandler } from './errorHandler';

export interface RequestConfig extends RequestInit {
  params?: Record<string, string | number>;
  timeout?: number;
  skipErrorHandling?: boolean;
}

export interface ApiResponse<T = any> {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
}

class HttpClient {
  private baseURL: string;
  private defaultHeaders: HeadersInit;
  private requestInterceptors: Array<(config: RequestConfig) => RequestConfig> = [];
  private responseInterceptors: Array<(response: Response) => Response | Promise<Response>> = [];

  constructor(baseURL: string = '', defaultHeaders: HeadersInit = {}) {
    this.baseURL = baseURL;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      ...defaultHeaders,
    };
  }

  /**
   * Set base URL for all requests
   */
  setBaseURL(url: string): void {
    this.baseURL = url;
  }

  /**
   * Set default headers for all requests
   */
  setDefaultHeaders(headers: HeadersInit): void {
    this.defaultHeaders = { ...this.defaultHeaders, ...headers };
  }

  /**
   * Add request interceptor
   */
  addRequestInterceptor(interceptor: (config: RequestConfig) => RequestConfig): void {
    this.requestInterceptors.push(interceptor);
  }

  /**
   * Add response interceptor
   */
  addResponseInterceptor(interceptor: (response: Response) => Response | Promise<Response>): void {
    this.responseInterceptors.push(interceptor);
  }

  /**
   * Build URL with query parameters
   */
  private buildURL(endpoint: string, params?: Record<string, string | number>): string {
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;
    
    if (!params || Object.keys(params).length === 0) {
      return url;
    }

    const queryString = Object.entries(params)
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
      .join('&');

    return `${url}?${queryString}`;
  }

  /**
   * Apply request interceptors
   */
  private applyRequestInterceptors(config: RequestConfig): RequestConfig {
    return this.requestInterceptors.reduce(
      (modifiedConfig, interceptor) => interceptor(modifiedConfig),
      config
    );
  }

  /**
   * Apply response interceptors
   */
  private async applyResponseInterceptors(response: Response): Promise<Response> {
    let modifiedResponse = response;
    for (const interceptor of this.responseInterceptors) {
      modifiedResponse = await interceptor(modifiedResponse);
    }
    return modifiedResponse;
  }

  /**
   * Core request method
   */
  private async request<T = any>(
    endpoint: string,
    config: RequestConfig = {}
  ): Promise<Response> {
    const {
      params,
      timeout,
      skipErrorHandling = false,
      headers = {},
      ...restConfig
    } = config;

    // Build URL
    const url = this.buildURL(endpoint, params);

    // Merge headers
    const mergedHeaders = {
      ...this.defaultHeaders,
      ...headers,
    };

    // Apply request interceptors
    let requestConfig: RequestConfig = this.applyRequestInterceptors({
      ...restConfig,
      headers: mergedHeaders,
    });

    // Setup timeout if specified
    let timeoutId: NodeJS.Timeout | undefined;
    const controller = new AbortController();
    
    if (timeout) {
      timeoutId = setTimeout(() => controller.abort(), timeout);
    }

    // Merge abort signals
    const signal = requestConfig.signal || controller.signal;

    try {
      const response = await fetch(url, {
        ...requestConfig,
        signal,
      });

      if (timeoutId) clearTimeout(timeoutId);

      // Apply response interceptors
      const interceptedResponse = await this.applyResponseInterceptors(response);

      // Handle errors if not skipped
      if (!interceptedResponse.ok && !skipErrorHandling) {
        await ApiErrorHandler.handleApiError(interceptedResponse, endpoint);
      }

      return interceptedResponse;
    } catch (error: any) {
      if (timeoutId) clearTimeout(timeoutId);

      // Don't log abort errors
      if (error.name === 'AbortError') {
        throw error;
      }

      // Handle network errors
      if (!skipErrorHandling) {
        ApiErrorHandler.handleNetworkError(error, endpoint);
      }

      throw error;
    }
  }

  /**
   * GET request
   */
  async get<T = any>(endpoint: string, config?: RequestConfig): Promise<Response> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'GET',
    });
  }

  /**
   * POST request
   */
  async post<T = any>(endpoint: string, data?: any, config?: RequestConfig): Promise<Response> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * PUT request
   */
  async put<T = any>(endpoint: string, data?: any, config?: RequestConfig): Promise<Response> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * PATCH request
   */
  async patch<T = any>(endpoint: string, data?: any, config?: RequestConfig): Promise<Response> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * DELETE request
   */
  async delete<T = any>(endpoint: string, config?: RequestConfig): Promise<Response> {
    return this.request<T>(endpoint, {
      ...config,
      method: 'DELETE',
    });
  }
}

// Create and export singleton instance
export const httpClient = new HttpClient();

// Export class for creating custom instances if needed
export default HttpClient;
