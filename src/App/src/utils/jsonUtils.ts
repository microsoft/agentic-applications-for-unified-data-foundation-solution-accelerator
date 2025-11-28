/**
 * JSON Utilities
 * Functions for parsing, sanitizing, and manipulating JSON strings
 */

/**
 * Remove a specific key from JSON object recursively
 */
export function removeKeyFromJSON(jsonString: string, keyToRemove: string): string {
  try {
    const obj = JSON.parse(jsonString);
    
    const removeKeyRecursive = (obj: any): any => {
      if (Array.isArray(obj)) {
        return obj.map((item: any) => removeKeyRecursive(item));
      } else if (obj !== null && typeof obj === 'object') {
        const newObj: Record<string, any> = {};
        for (const key in obj) {
          if (obj.hasOwnProperty(key) && key !== keyToRemove) {
            newObj[key] = removeKeyRecursive(obj[key]);
          }
        }
        return newObj;
      }
      return obj;
    };
    
    const result = removeKeyRecursive(obj);
    return JSON.stringify(result);
  } catch (error) {
    console.error('Error parsing JSON:', error);
    return jsonString;
  }
}

/**
 * Find matching closing bracket for a given opening bracket
 */
function findMatchingBracket(str: string, startIndex: number): number {
  let depth = 0;
  const openBracket = str[startIndex];
  const closeBracket = openBracket === '{' ? '}' : ')';
  
  for (let i = startIndex; i < str.length; i++) {
    if (str[i] === openBracket || (openBracket === '(' && str[i] === '{')) {
      depth++;
    } else if (str[i] === closeBracket || (closeBracket === ')' && str[i] === '}')) {
      depth--;
      if (depth === 0) {
        return i;
      }
    }
  }
  return -1;
}

/**
 * Sanitize malformed JSON string to make it parseable
 */
export function sanitizeJSONString(jsonString: string): string {
  if (!jsonString || typeof jsonString !== 'string') {
    return jsonString;
  }

  let sanitized = jsonString;

  try {
    // **STEP 1: Try parsing first - if it works, no sanitization needed!**
    try {
      JSON.parse(sanitized);
      return sanitized;
    } catch {
      // JSON invalid, proceed with sanitization
    }

    // **STEP 2: Handle escaped JSON strings (e.g., "{\"type\":\"bar\"...}")**
    if (sanitized.startsWith('"{') && sanitized.endsWith('}"')) {
      sanitized = sanitized.slice(1, -1);
    }
    
    // **STEP 3: ALWAYS unescape backslashes**
    sanitized = sanitized.replace(/\\"/g, '"');
    sanitized = sanitized.replace(/\\\\/g, '\\');
    sanitized = sanitized.replace(/\\n/g, '\n');
    sanitized = sanitized.replace(/\\r/g, '\r');
    sanitized = sanitized.replace(/\\t/g, '\t');

    // **STEP 4: Validate after basic unescaping**
    try {
      JSON.parse(sanitized);
      return sanitized;
    } catch {
      // Still invalid, continue with complex sanitization
    }

    // **STEP 5: Remove function declarations with balanced brackets**
    let pos = 0;
    while (pos < sanitized.length) {
      const functionMatch = sanitized.substring(pos).match(/:\s*function\s*\w*\s*\(/);
      if (!functionMatch) break;
      
      const functionStart = pos + functionMatch.index!;
      const parenStart = sanitized.indexOf('(', functionStart);
      if (parenStart === -1) break;
      
      const parenEnd = findMatchingBracket(sanitized, parenStart);
      if (parenEnd === -1) break;
      
      const braceStart = sanitized.indexOf('{', parenEnd);
      if (braceStart === -1 || braceStart > parenEnd + 10) {
        pos = parenEnd + 1;
        continue;
      }
      
      const braceEnd = findMatchingBracket(sanitized, braceStart);
      if (braceEnd === -1) break;
      
      sanitized = 
        sanitized.substring(0, functionStart) + 
        ': "[Function]"' + 
        sanitized.substring(braceEnd + 1);
      
      pos = functionStart + 13;
    }

    // **STEP 6: Remove arrow functions with balanced brackets**
    pos = 0;
    while (pos < sanitized.length) {
      const arrowMatch = sanitized.substring(pos).match(/:\s*\([^)]*\)\s*=>\s*\{/);
      if (!arrowMatch) break;
      
      const arrowStart = pos + arrowMatch.index!;
      const braceStart = sanitized.indexOf('{', arrowStart);
      if (braceStart === -1) break;
      
      const braceEnd = findMatchingBracket(sanitized, braceStart);
      if (braceEnd === -1) break;
      
      sanitized = 
        sanitized.substring(0, arrowStart) + 
        ': "[Function]"' + 
        sanitized.substring(braceEnd + 1);
      
      pos = arrowStart + 13;
    }

    // **STEP 7: Remove standalone function patterns**
    pos = 0;
    while (pos < sanitized.length) {
      const funcMatch = sanitized.substring(pos).match(/\bfunction\s*\w*\s*\(/);
      if (!funcMatch) break;
      
      const funcStart = pos + funcMatch.index!;
      if (funcStart > 0 && sanitized.substring(Math.max(0, funcStart - 10), funcStart).includes(':')) {
        pos = funcStart + 1;
        continue;
      }
      
      const parenStart = sanitized.indexOf('(', funcStart);
      if (parenStart === -1) break;
      
      const parenEnd = findMatchingBracket(sanitized, parenStart);
      if (parenEnd === -1) break;
      
      const braceStart = sanitized.indexOf('{', parenEnd);
      if (braceStart === -1 || braceStart > parenEnd + 10) {
        pos = parenEnd + 1;
        continue;
      }
      
      const braceEnd = findMatchingBracket(sanitized, braceStart);
      if (braceEnd === -1) break;
      
      sanitized = 
        sanitized.substring(0, funcStart) + 
        '"[Function]"' + 
        sanitized.substring(braceEnd + 1);
      
      pos = funcStart + 12;
    }

    // **STEP 8-11: Other sanitization patterns**
    sanitized = sanitized.replace(/:\s*\([^)]*\)\s*=>\s*`[^`]*`/g, ': "[Function]"');
    sanitized = sanitized.replace(/:\s*\([^)]*\)\s*=>\s*[^,}\]]+/g, ': "[Function]"');
    sanitized = sanitized.replace(/\([^)]*\)\s*=>/g, '"[Function]"');
    sanitized = sanitized.replace(/\$\{[^}]*\}/g, '[Expression]');
    sanitized = sanitized.replace(/`[^`]*`/g, '"[Template]"');
    sanitized = sanitized.replace(/:\s*'([^']*)'/g, ': "$1"');
    sanitized = sanitized.replace(/,(\s*[}\]])/g, '$1');
    sanitized = sanitized.replace(/([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:/g, '$1"$2":');
    
    // Count all brackets
    const openBraces = (sanitized.match(/\{/g) || []).length;
    const closeBraces = (sanitized.match(/\}/g) || []).length;
    const openBrackets = (sanitized.match(/\[/g) || []).length;
    const closeBrackets = (sanitized.match(/\]/g) || []).length;
    
    // **AUTO-REPAIR: Add missing closing brackets**
    if (openBraces > closeBraces) {
      const missing = openBraces - closeBraces;
      sanitized += '}'.repeat(missing);
    }
    
    if (openBrackets > closeBrackets) {
      const missing = openBrackets - closeBrackets;
      sanitized += ']'.repeat(missing);
    }
    
    // **AUTO-REPAIR: Remove excess closing brackets**
    if (closeBraces > openBraces) {
      let excess = closeBraces - openBraces;
      while (excess > 0 && sanitized.endsWith('}')) {
        sanitized = sanitized.slice(0, -1);
        excess--;
      }
    }
    
    if (closeBrackets > openBrackets) {
      let excess = closeBrackets - openBrackets;
      while (excess > 0 && sanitized.endsWith(']')) {
        sanitized = sanitized.slice(0, -1);
        excess--;
      }
    }
    
    // **FINAL PARSE TEST**
    try {
      JSON.parse(sanitized);
      return sanitized;
    } catch (finalError) {
      console.error("Parse error:", finalError instanceof Error ? finalError.message : String(finalError));

      // Try to extract valid JSON object
      try {
        const firstBraceIndex = sanitized.indexOf('{');
        if (firstBraceIndex !== -1) {
          let depth = 0;
          let endIndex = -1;
          
          for (let i = firstBraceIndex; i < sanitized.length; i++) {
            if (sanitized[i] === '{') depth++;
            else if (sanitized[i] === '}') {
              depth--;
              if (depth === 0) {
                endIndex = i;
                break;
              }
            }
          }
          
          if (endIndex !== -1) {
            const extracted = sanitized.substring(firstBraceIndex, endIndex + 1);
            JSON.parse(extracted); // Test if valid
            return extracted;
          }
        }
      } catch (extractError) {
        console.error("Extraction attempt also failed");
      }
      
      // Return original string as last resort
      console.warn("Returning original string - all repair attempts failed");
      return jsonString;
    }
  } catch (error) {
    console.error("Unexpected error during sanitization:", error);
    return jsonString;
  }
}

/**
 * Parse nested answer string (handles double-escaped JSON)
 */
export function parseNestedAnswer(answerValue: string): any {
  const updatedJsonstring = removeKeyFromJSON(answerValue, 'tooltip');
  try {
    // Attempt 1: Direct parse
    return JSON.parse(updatedJsonstring);
  } catch {
    // Attempt 2: Sanitize then parse
    const sanitized = sanitizeJSONString(updatedJsonstring);
    
    const openBraces = (sanitized.match(/\{/g) || []).length;
    const closeBraces = (sanitized.match(/\}/g) || []).length;
    
    if (openBraces !== closeBraces) {
      throw new Error("Sanitization produced unbalanced braces");
    }
    
    return JSON.parse(sanitized);
  }
}

/**
 * Parse chart content from raw response string
 */
export function parseChartContent(rawContent: string): any {
  const updatedJsonstring = removeKeyFromJSON(rawContent, 'tooltip');
  try {
    const chartResponse = JSON.parse(updatedJsonstring);
    
    // Handle nested escaped JSON in "answer" field
    if (chartResponse && typeof chartResponse === "object" && "answer" in chartResponse) {
      const answerValue = chartResponse.answer;
      
      if (typeof answerValue === "string") {
        try {
          chartResponse.answer = parseNestedAnswer(answerValue);
        } catch (nestedError) {
          console.error("Nested parse error:", nestedError instanceof Error ? nestedError.message : String(nestedError));
        }
      }
    }
    
    return chartResponse;
  } catch {
    console.error("Failed to parse raw content, trying sanitization...");
    
    const sanitized = removeKeyFromJSON(sanitizeJSONString(updatedJsonstring), 'tooltip');
    try {
      return JSON.parse(sanitized);
    } catch (sanitizeError) {
      console.error("JSON parse failed after sanitization:", sanitizeError instanceof Error ? sanitizeError.message : String(sanitizeError));
      return "Chart can't be generated, please try again.";
    }
  }
}

/**
 * Check if error message is malformed chart JSON
 */
export function isMalformedChartJSON(errorMsg: string, hasBackendError: boolean): boolean {
  return typeof errorMsg === "string" &&
    !hasBackendError &&
    (errorMsg.includes('"type"') || errorMsg.includes('"chartType"')) &&
    errorMsg.includes('"data"') &&
    (errorMsg.includes('{') || errorMsg.includes('}'));
}

/**
 * Safe JSON parse with fallback
 */
export function safeJSONParse<T = any>(jsonString: string, fallback: T | null = null): T | null {
  try {
    return JSON.parse(jsonString);
  } catch (error) {
    console.error('Failed to parse JSON:', error);
    return fallback;
  }
}
