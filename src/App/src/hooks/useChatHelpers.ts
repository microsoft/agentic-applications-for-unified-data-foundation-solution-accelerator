/**
 * Custom Hooks for Chat Component
 * Extracted complex logic into reusable hooks
 */

import { useCallback, useRef, useEffect, useState } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import {
  setGeneratingResponse,
  addMessages,
  setStreamingFlag,
} from '../store/chatSlice';
import { setHistoryUpdateAPIPending } from '../store/chatHistorySlice';
import { ChatMessage, ConversationRequest, ChartDataResponse } from '../types/AppTypes';
import { callConversationApi, historyUpdate } from '../api/api';
import { generateUUIDv4 } from '../configs/Utils';
import { isChartQuery, parseChartResponse, extractChartError } from '../utils/chartUtils';
import { createUserMessage, createAssistantMessage, createErrorMessage, MessageRole } from '../utils/messageUtils';

/**
 * Hook for managing chat API requests
 */
export function useChatApi() {
  const dispatch = useAppDispatch();
  const abortFuncs = useRef<AbortController[]>([]);

  const makeApiRequest = useCallback(async (
    question: string,
    conversationId: string,
    onSuccess?: (messages: ChatMessage[]) => void,
    onError?: (error: Error) => void
  ) => {
    if (!question.trim()) return;

    const newMessage = createUserMessage(question);
    dispatch(addMessages([newMessage]));

    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      query: question,
    };

    let updatedMessages: ChatMessage[] = [];

    try {
      dispatch(setGeneratingResponse(true));
      const response = await callConversationApi(request, abortController.signal);

      if (response?.body) {
        const reader = response.body.getReader();
        let runningText = '';
        let hasError = false;

        // Read stream
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = new TextDecoder('utf-8').decode(value);
          try {
            const textObj = JSON.parse(text);
            if (textObj?.object?.data) {
              runningText = text;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = text;
            }
          } catch (e) {
            // Non-JSON chunk, continue
          }
        }

        // Process response
        if (hasError) {
          const errorMsg = JSON.parse(runningText).error;
          const errorMessage = createErrorMessage(errorMsg);
          updatedMessages = [newMessage, errorMessage];
        } else if (isChartQuery(question)) {
          const parsedResponse = parseChartResponse(runningText);

          if (parsedResponse) {
            const chartMessage = createAssistantMessage(parsedResponse);
            updatedMessages = [newMessage, chartMessage];
          } else {
            const error = extractChartError(JSON.parse(runningText));
            if (error) {
              const errorMessage = createErrorMessage(error);
              updatedMessages = [newMessage, errorMessage];
            }
          }
        }
      }

      if (updatedMessages.length > 0 && onSuccess) {
        onSuccess(updatedMessages);
      }

      return updatedMessages;
    } catch (e) {
      console.error('Error in makeApiRequest:', e);

      if (abortController.signal.aborted) {
        updatedMessages = [newMessage];
      } else if (e instanceof Error) {
        if (onError) {
          onError(e);
        }
      }
      return updatedMessages;
    } finally {
      dispatch(setGeneratingResponse(false));
    }
  }, [dispatch]);

  const stopGenerating = useCallback(() => {
    abortFuncs.current.forEach((abortController) => abortController.abort());
    dispatch(setGeneratingResponse(false));
    dispatch(setStreamingFlag(false));
  }, [dispatch]);

  return {
    makeApiRequest,
    stopGenerating,
  };
}

/**
 * Hook for managing chat history save operations
 */
export function useChatHistorySave() {
  const dispatch = useAppDispatch();

  const saveToDB = useCallback(async (
    newMessages: ChatMessage[],
    convId: string,
    options?: {
      isNewConversation?: boolean;
      onSuccess?: (conversationId: string) => void;
      onError?: (error: Error) => void;
    }
  ) => {
    if (!convId || !newMessages.length) {
      return;
    }

    dispatch(setHistoryUpdateAPIPending(true));

    try {
      const res = await historyUpdate(newMessages, convId);

      if (!res.ok) {
        throw new Error('Failed to save history');
      }

      const responseJson = await res.json();

      if (responseJson?.success && options?.onSuccess) {
        options.onSuccess(convId);
      }
    } catch (error) {
      console.error('Error saving to DB:', error);
      if (options?.onError && error instanceof Error) {
        options.onError(error);
      }
    } finally {
      dispatch(setHistoryUpdateAPIPending(false));
    }
  }, [dispatch]);

  return { saveToDB };
}

/**
 * Hook for auto-scrolling chat to bottom
 */
export function useAutoScroll(dependencies: any[] = []) {
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback(() => {
    if (chatMessageStreamEnd.current) {
      chatMessageStreamEnd.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, dependencies);

  return { chatMessageStreamEnd, scrollToBottom };
}

/**
 * Hook for managing textarea auto-resize
 */
export function useTextareaAutoResize(textareaRef: React.RefObject<HTMLTextAreaElement>) {
  const adjustTextareaHeight = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [textareaRef]);

  return { adjustTextareaHeight };
}

/**
 * Hook for debounced value
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
