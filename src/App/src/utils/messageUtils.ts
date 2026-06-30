/**
 * Message Utilities
 * Functions for message parsing and transformation
 */

/**
 * Extracts answer text and citations from API response content
 * Parses JSON-like response to separate answer from citations
 */
export function extractAnswerAndCitations(responseContent: string): { answerText: string; citationString: string } {
  let answerText = '';
  let citationString = '';

  const answerKey = `"answer":`;
  const answerStartIndex = responseContent.indexOf(answerKey);

  // If no "answer" key found, treat the entire response as plain text
  if (answerStartIndex === -1) {
    return { answerText: responseContent, citationString: '' };
  }

  const answerTextStart = answerStartIndex + 9;
  const citationsKey = `"citations":`;
  const citationsStartIndex = responseContent.indexOf(citationsKey);

  if (citationsStartIndex > answerTextStart) {
    answerText = responseContent.substring(answerTextStart, citationsStartIndex).trim();
    citationString = responseContent.substring(citationsStartIndex).trim();
  } else {
    answerText = responseContent.substring(answerTextStart).trim();
  }

  answerText = answerText
    .replace(/^"+|"+$|,$/g, '')
    .replace(/[",]+$/, '')
    .replace(/\\n/g, "  \n");

  return { answerText, citationString };
}
