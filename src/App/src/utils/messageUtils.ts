/**
 * Message Utilities
 * Functions for message creation, parsing, and transformation
 */

import { ChatMessage, ChartDataResponse, ToolMessageContent } from '../types/AppTypes';
import { generateUUIDv4 } from '../configs/Utils';

/**
 * Message role constants
 */
export const MessageRole = {
  ASSISTANT: 'assistant' as const,
  USER: 'user' as const,
  TOOL: 'tool' as const,
  ERROR: 'error' as const,
};

export type MessageRoleType = typeof MessageRole[keyof typeof MessageRole];

/**
 * Create a new chat message
 */
export function createChatMessage(
  role: MessageRoleType,
  content: string | ChartDataResponse,
  options: Partial<ChatMessage> = {}
): ChatMessage {
  return {
    id: generateUUIDv4(),
    role,
    content,
    date: new Date().toISOString(),
    ...options,
  };
}

/**
 * Create user message
 */
export function createUserMessage(content: string): ChatMessage {
  return createChatMessage(MessageRole.USER, content);
}

/**
 * Create assistant message
 */
export function createAssistantMessage(
  content: string | ChartDataResponse
): ChatMessage {
  return createChatMessage(MessageRole.ASSISTANT, content);
}

/**
 * Create error message
 */
export function createErrorMessage(error: string | Error): ChatMessage {
  const errorContent = typeof error === 'string' ? error : error.message;
  return createChatMessage(MessageRole.ERROR, errorContent);
}

/**
 * Create tool message
 */
export function createToolMessage(content: string): ChatMessage {
  return createChatMessage(MessageRole.TOOL, content);
}

/**
 * Check if message is a chart response
 */
export function isChartMessage(message: ChatMessage): boolean {
  if (typeof message.content === 'object' && message.content !== null) {
    const content = message.content as any;
    return !!(content.type || content.chartType) && !!content.data;
  }
  return false;
}

/**
 * Check if message is an error message
 */
export function isErrorMessage(message: ChatMessage): boolean {
  return message.role === MessageRole.ERROR;
}

/**
 * Check if message is from user
 */
export function isUserMessage(message: ChatMessage): boolean {
  return message.role === MessageRole.USER;
}

/**
 * Check if message is from assistant
 */
export function isAssistantMessage(message: ChatMessage): boolean {
  return message.role === MessageRole.ASSISTANT;
}

/**
 * Get message content as string
 */
export function getMessageContentAsString(message: ChatMessage): string {
  if (typeof message.content === 'string') {
    return message.content;
  }
  
  if (typeof message.content === 'object') {
    return JSON.stringify(message.content);
  }
  
  return '';
}

/**
 * Validate message structure
 */
export function isValidMessage(message: any): message is ChatMessage {
  return (
    message &&
    typeof message === 'object' &&
    typeof message.id === 'string' &&
    typeof message.role === 'string' &&
    message.content !== undefined &&
    typeof message.date === 'string'
  );
}

/**
 * Filter messages by role
 */
export function filterMessagesByRole(
  messages: ChatMessage[],
  role: MessageRoleType | MessageRoleType[]
): ChatMessage[] {
  const roles = Array.isArray(role) ? role : [role];
  return messages.filter(msg => roles.includes(msg.role as MessageRoleType));
}

/**
 * Get last message from array
 */
export function getLastMessage(messages: ChatMessage[]): ChatMessage | null {
  return messages.length > 0 ? messages[messages.length - 1] : null;
}

/**
 * Get last message by role
 */
export function getLastMessageByRole(
  messages: ChatMessage[],
  role: MessageRoleType
): ChatMessage | null {
  const filtered = filterMessagesByRole(messages, role);
  return getLastMessage(filtered);
}

/**
 * Update message by ID
 */
export function updateMessageInArray(
  messages: ChatMessage[],
  messageId: string,
  updates: Partial<ChatMessage>
): ChatMessage[] {
  return messages.map(msg =>
    msg.id === messageId ? { ...msg, ...updates } : msg
  );
}

/**
 * Remove message by ID
 */
export function removeMessageFromArray(
  messages: ChatMessage[],
  messageId: string
): ChatMessage[] {
  return messages.filter(msg => msg.id !== messageId);
}

/**
 * Sort messages by date
 */
export function sortMessagesByDate(
  messages: ChatMessage[],
  order: 'asc' | 'desc' = 'asc'
): ChatMessage[] {
  return [...messages].sort((a, b) => {
    const dateA = new Date(a.date).getTime();
    const dateB = new Date(b.date).getTime();
    return order === 'asc' ? dateA - dateB : dateB - dateA;
  });
}

/**
 * Group messages by date
 */
export function groupMessagesByDate(
  messages: ChatMessage[]
): Record<string, ChatMessage[]> {
  return messages.reduce((groups, message) => {
    const date = new Date(message.date).toDateString();
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(message);
    return groups;
  }, {} as Record<string, ChatMessage[]>);
}

/**
 * Count messages by role
 */
export function countMessagesByRole(messages: ChatMessage[]): Record<string, number> {
  return messages.reduce((counts, message) => {
    counts[message.role] = (counts[message.role] || 0) + 1;
    return counts;
  }, {} as Record<string, number>);
}

/**
 * Truncate message content
 */
export function truncateMessageContent(
  message: ChatMessage,
  maxLength: number = 100
): string {
  const content = getMessageContentAsString(message);
  return content.length > maxLength
    ? `${content.substring(0, maxLength)}...`
    : content;
}

/**
 * Clone message (deep copy)
 */
export function cloneMessage(message: ChatMessage): ChatMessage {
  return {
    ...message,
    content:
      typeof message.content === 'object'
        ? JSON.parse(JSON.stringify(message.content))
        : message.content,
    citations: message.citations,
    context: message.context,
  };
}

/**
 * Merge messages removing duplicates by ID
 */
export function mergeMessages(
  messages1: ChatMessage[],
  messages2: ChatMessage[]
): ChatMessage[] {
  const messageMap = new Map<string, ChatMessage>();
  
  [...messages1, ...messages2].forEach(msg => {
    messageMap.set(msg.id, msg);
  });
  
  return Array.from(messageMap.values());
}

/**
 * Extract answer text and citations from response content
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
