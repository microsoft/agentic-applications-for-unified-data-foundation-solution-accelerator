/**
 * Chart Utilities
 * Functions for chart-related operations
 */

import { ChartDataResponse } from '../types/AppTypes';

/**
 * Chart-related keywords for query detection
 */
const CHART_KEYWORDS = [
  'chart',
  'graph',
  'plot',
  'visualize',
  'visualization',
  'diagram',
  'show',
  'display',
  'bar chart',
  'line chart',
  'pie chart',
  'scatter',
  'histogram',
];

/**
 * Check if query is requesting a chart
 */
export function isChartQuery(query: string): boolean {
  if (!query || typeof query !== 'string') {
    return false;
  }

  const lowerQuery = query.toLowerCase().trim();
  
  return CHART_KEYWORDS.some(keyword => lowerQuery.includes(keyword));
}

/**
 * Validate chart data response
 */
export function isValidChartResponse(data: any): data is ChartDataResponse {
  if (!data || typeof data !== 'object') {
    return false;
  }

  // Check for required chart properties
  const hasType = !!data.type;
  const hasData = !!data.data;

  return hasType && hasData;
}

/**
 * Extract chart type from response
 */
export function getChartType(data: ChartDataResponse): string {
  return data.type || 'unknown';
}

/**
 * Parse chart response from JSON string
 */
export function parseChartResponse(jsonString: string): ChartDataResponse | null {
  try {
    const parsed = JSON.parse(jsonString);
    
    // Handle nested object structure
    if (parsed?.object && isValidChartResponse(parsed.object)) {
      return parsed.object as ChartDataResponse;
    }
    
    // Handle direct chart data
    if (isValidChartResponse(parsed)) {
      return parsed as ChartDataResponse;
    }
    
    return null;
  } catch (error) {
    console.error('Failed to parse chart response:', error);
    return null;
  }
}

/**
 * Extract error message from chart response
 */
export function extractChartError(data: any): string | null {
  if (!data || typeof data !== 'object') {
    return null;
  }

  // Check for error property
  if (data.error && typeof data.error === 'string') {
    return data.error;
  }

  // Check for nested error in object
  if (data.object?.error && typeof data.object.error === 'string') {
    return data.object.error;
  }

  // Check for message property (sometimes used for errors)
  if (data.message && typeof data.message === 'string') {
    return data.message;
  }

  if (data.object?.message && typeof data.object.message === 'string') {
    return data.object.message;
  }

  return null;
}

/**
 * Normalize chart data structure
 */
export function normalizeChartData(data: ChartDataResponse): ChartDataResponse {
  return {
    answer: data.answer || '',
    type: data.type,
    data: data.data,
    options: data.options,
  };
}

/**
 * Get chart display configuration
 */
export function getChartDisplayConfig(chartType: string): {
  width: string | number;
  height: string | number;
  responsive: boolean;
} {
  const configs: Record<string, any> = {
    bar: { width: '100%', height: 400, responsive: true },
    line: { width: '100%', height: 400, responsive: true },
    pie: { width: '100%', height: 400, responsive: true },
    scatter: { width: '100%', height: 400, responsive: true },
    default: { width: '100%', height: 400, responsive: true },
  };

  return configs[chartType.toLowerCase()] || configs.default;
}

/**
 * Validate chart data structure
 */
export function validateChartData(data: any): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (!data) {
    errors.push('Chart data is null or undefined');
    return { valid: false, errors };
  }

  if (typeof data !== 'object') {
    errors.push('Chart data must be an object');
    return { valid: false, errors };
  }

  if (!data.type && !data.chartType) {
    errors.push('Chart type is required');
  }

  if (!data.data) {
    errors.push('Chart data property is required');
  } else if (!Array.isArray(data.data) && typeof data.data !== 'object') {
    errors.push('Chart data must be an array or object');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Extract chart keywords from query
 */
export function extractChartKeywords(query: string): string[] {
  const lowerQuery = query.toLowerCase();
  return CHART_KEYWORDS.filter(keyword => lowerQuery.includes(keyword));
}

/**
 * Determine chart type from query
 */
export function inferChartTypeFromQuery(query: string): string | null {
  const lowerQuery = query.toLowerCase();

  if (lowerQuery.includes('bar')) return 'bar';
  if (lowerQuery.includes('line')) return 'line';
  if (lowerQuery.includes('pie')) return 'pie';
  if (lowerQuery.includes('scatter')) return 'scatter';
  if (lowerQuery.includes('histogram')) return 'histogram';
  if (lowerQuery.includes('area')) return 'area';

  return null;
}

/**
 * Format chart data for display
 */
export function formatChartDataForDisplay(data: ChartDataResponse): string {
  const chartType = getChartType(data);
  const dataPoints = Array.isArray(data.data) ? data.data.length : 'N/A';

  return `Chart Type: ${chartType}, Data Points: ${dataPoints}`;
}

/**
 * Check if chart needs loading state
 */
export function shouldShowChartLoading(query: string): boolean {
  return isChartQuery(query);
}

/**
 * Generate chart title from query
 */
export function generateChartTitle(query: string): string {
  // Remove chart-related keywords
  let title = query;
  CHART_KEYWORDS.forEach(keyword => {
    const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
    title = title.replace(regex, '');
  });

  // Clean up extra spaces
  title = title.trim().replace(/\s+/g, ' ');

  // Capitalize first letter
  return title.charAt(0).toUpperCase() + title.slice(1);
}
