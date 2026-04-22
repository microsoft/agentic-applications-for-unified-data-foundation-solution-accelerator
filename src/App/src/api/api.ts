import {
  historyListResponse,
  historyReadResponse,
} from "../configs/StaticData";
import {
  ChatMessage,
  Conversation,
  ConversationRequest,
} from "../types/AppTypes";
import { ApiErrorHandler } from "../utils/errorHandler";
import { getApiBaseUrl, isWorkShopDeployment } from "../config";
import { httpClient } from "../utils/httpClient";
import { getUserId, setUserId, getAccessToken, setAccessToken, createErrorResponse } from "../utils/apiUtils";

const baseURL = getApiBaseUrl(); // base API URL

// Get history base path based on deployment mode
function getHistoryBasePath(): string {
  const isWorkshop = isWorkShopDeployment();
  const basePath = isWorkshop ? '/history' : '/historyfab';
  return basePath;
}

// Initialize HTTP client with base URL
httpClient.setBaseURL(baseURL);

// Add user ID and access token to all requests via interceptor
httpClient.addRequestInterceptor((config) => {
  const userId = getUserId();
  if (userId && config.headers) {
    (config.headers as any)['X-Ms-Client-Principal-Id'] = userId;
  }
  // Add access token for cross-domain auth and OBO flow
  // EasyAuth accepts Bearer token in Authorization header for cross-origin requests
  const accessToken = getAccessToken();
  console.log('[Request] accessToken from sessionStorage:', accessToken ? `${accessToken.substring(0, 20)}...` : 'NULL');
  if (accessToken && config.headers) {
    (config.headers as any)['Authorization'] = `Bearer ${accessToken}`;
    // Also send as X-ZUMO-AUTH for App Service EasyAuth compatibility
    (config.headers as any)['X-ZUMO-AUTH'] = accessToken;
    console.log('[Request] Added X-ZUMO-AUTH header');
  } else {
    console.log('[Request] NO token - Authorization and X-ZUMO-AUTH headers NOT added');
  }
  return config;
});

export type UserInfo = {
  access_token: string;
  expires_on: string;
  id_token: string;
  provider_name: string;
  user_claims: any[];
  user_id: string;
};

export async function getUserInfo(): Promise<UserInfo[]> {
  const response = await fetch(`/.auth/me`, {
    credentials: 'include'  // Ensure cookies are sent for EasyAuth session
  });
  if (!response.ok) {
    // Use new error handling system
    await ApiErrorHandler.handleApiError(response, '/.auth/me');
    // console.error("No identity provider found. Access to chat will be blocked.");
    return [];
  }
  const payload = await response.json();
  
  // Debug: Log the full auth/me response to understand token availability
  console.log('[Auth] /.auth/me response:', JSON.stringify(payload, null, 2));
  
  const userClaims = payload[0]?.user_claims || [];
  const objectIdClaim = userClaims.find(
    (claim: any) =>
      claim.typ === "http://schemas.microsoft.com/identity/claims/objectidentifier"
  );
  const userId = objectIdClaim?.val;
  if (userId) {
    setUserId(userId);
  }
  // Store access token for OBO flow (needed for Work IQ Teams)
  const accessToken = payload[0]?.access_token;
  console.log('[Auth] access_token present:', !!accessToken);
  console.log('[Auth] access_token value:', accessToken ? `${accessToken.substring(0, 30)}...` : 'NULL');
  if (accessToken) {
    setAccessToken(accessToken);
    console.log('[Auth] Token stored in sessionStorage');
    // Verify it was stored
    const storedToken = getAccessToken();
    console.log('[Auth] Verified stored token:', storedToken ? `${storedToken.substring(0, 30)}...` : 'NULL');
  } else {
    console.log('[Auth] NO access_token to store!');
  }
  return payload;
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  const endpoint = `${getHistoryBasePath()}/read`;
  
  try {
    const response = await httpClient.get(endpoint, {
      params: { id: convId }
    });
    
    if (!response.ok) {
      // Return fallback data (maintaining current behavior)
      return historyReadResponse.messages.map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        date: msg.createdAt,
        feedback: msg.feedback ?? undefined,
        context: msg.context,
        contentType: msg.contentType,
      }));
    }

    const payload = await response.json();
    const messages: ChatMessage[] = [];

    if (Array.isArray(payload?.messages)) {
      payload.messages.forEach((msg: any) => {
        const message: ChatMessage = {
          id: msg.id,
          role: msg.role,
          content: msg.content,
          date: msg.createdAt,
          feedback: msg.feedback ?? undefined,
          context: msg.context,
          citations: msg.citations,
          contentType: msg.contentType,
        };
        messages.push(message);
      });
    }
    return messages;
    
  } catch (error) {
    return [];
  }
};

export const historyList = async (
  offset = 0,
  limit = 25
): Promise<Conversation[] | null> => {
  const endpoint = `${getHistoryBasePath()}/list`;
  
  try {
    const response = await httpClient.get(endpoint, {
      params: { offset, limit }
    });

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    
    if (!Array.isArray(payload)) {
      // Log as general error
      ApiErrorHandler.handleGeneralError(
        new Error("Invalid response format: expected array"), 
        endpoint
      );
      return null;
    }
    
    const conversations: Conversation[] = payload.map((conv: any) => {
      const conversation: Conversation = {
        // Use conversationId as fallback if id is not available
        id: conv.id || conv.conversation_id,
        title: conv.title,
        date: conv.createdAt,
        updatedAt: conv?.updatedAt,
        messages: [],
      };
      return conversation;
    });
    return conversations;
    
  } catch (error) {
    // Use new error handling system with fallback data
    ApiErrorHandler.handleNetworkError(error, endpoint);
    
    // Return fallback data (maintaining current behavior)
    const conversations: Conversation[] = historyListResponse.map(
      (conv: any) => {
        const conversation: Conversation = {
          // Use conversationId as fallback if id is not available
          id: conv.id || conv.conversation_id,
          title: conv.title,
          date: conv.createdAt,
          updatedAt: conv?.updatedAt,
          messages: [],
        };
        return conversation;
      }
    );
    return conversations;
  }
};

export const historyUpdate = async (
  newMessages: ChatMessage[],
  convId: string
): Promise<Response> => {
  const endpoint = `${getHistoryBasePath()}/update`;
  
  try {
    const response = await httpClient.post(endpoint, {
      conversation_id: convId,
      messages: newMessages,
    });
    
    return response;
    
  } catch (error) {
    // Return error response (maintaining current behavior)
    return createErrorResponse(500, 'Failed to update history');
  }
};

export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const endpoint = `/api/chat`;
  
  try {
    const response = await httpClient.post(endpoint, {
      conversation_id: options.id,
      query: options.query
    }, {
      signal: abortSignal
    });

    if (!response.ok) {
      // Handle error with new system but still throw (maintaining current behavior)
      const errorInfo = await ApiErrorHandler.handleApiError(response, endpoint);
      
      try {
        const errorData = await response.json();
        throw new Error(JSON.stringify(errorData.error));
      } catch (parseError) {
        throw new Error(errorInfo.message);
      }
    }

    return response;
    
  } catch (error: any) {
    // Log network errors
    if (error.name !== 'AbortError') {
      ApiErrorHandler.handleNetworkError(error, endpoint);
    }
    throw error; // Re-throw to maintain current behavior
  }
}

export const historyRename = async (
  convId: string,
  title: string
): Promise<Response> => {
  const endpoint = `${getHistoryBasePath()}/rename`;
  
  try {
    const response = await httpClient.post(endpoint, {
      conversation_id: convId,
      title: title,
    });
    
    return response;
    
  } catch (error) {
    // Return error response (maintaining current behavior)
    return createErrorResponse(500, 'Failed to rename conversation');
  }
};

export const historyDelete = async (convId: string): Promise<Response> => {
  const endpoint = `${getHistoryBasePath()}/delete`;
  
  try {
    const response = await httpClient.delete(endpoint, {
      params: { id: convId }
    });
    
    return response;
    
  } catch (error) {
    // Return error response (maintaining current behavior)
    return createErrorResponse(500, 'Failed to delete conversation');
  }
};

export const historyDeleteAll = async (): Promise<Response> => {
  const endpoint = `${getHistoryBasePath()}/delete_all`;
  
  try {
    const response = await httpClient.delete(endpoint, {
      body: JSON.stringify({})
    });
    
    return response;
    
  } catch (error) {
    // Return error response (maintaining current behavior)
    return createErrorResponse(500, 'Failed to delete all conversations');
  }
};

export const fetchCitationContent = async (body: any) => {
  const endpoint = `/api/fetch-azure-search-content`;
  
  try {
    const response = await httpClient.post(endpoint, body);
    
    if (!response.ok) {
      // Handle error with new system and throw (maintaining current behavior)
      const errorInfo = await ApiErrorHandler.handleApiError(response, endpoint);
      throw new Error(errorInfo.message);
    }
    
    const data = await response.json();
    return data;
    
  } catch (error: any) {
    // Use new error handling system
    if (error.message && !error.message.includes('Failed to fetch')) {
      // If it's already our formatted error, just re-throw
      throw error;
    } else {
      // Handle network errors
      const errorInfo = ApiErrorHandler.handleNetworkError(error, endpoint);
      throw new Error(errorInfo.message);
    }
  }
};
