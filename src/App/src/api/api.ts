import {
  historyListResponse,
  historyReadResponse,
} from "../configs/StaticData";
import {
  AppConfig,
  ChartConfigItem,
  ChatMessage,
  Conversation,
  ConversationRequest,
  CosmosDBHealth,
  CosmosDBStatus,
} from "../types/AppTypes";
import { ApiErrorHandler } from "../utils/errorHandler";

const baseURL = process.env.REACT_APP_API_BASE_URL;// base API URL

export type UserInfo = {
  access_token: string;
  expires_on: string;
  id_token: string;
  provider_name: string;
  user_claims: any[];
  user_id: string;
};

export async function getUserInfo(): Promise<UserInfo[]> {
  const response = await fetch(`/.auth/me`);
  if (!response.ok) {
    // Use new error handling system
    await ApiErrorHandler.handleApiError(response, '/.auth/me');
    console.error("No identity provider found. Access to chat will be blocked.");
    return [];
  }
  const payload = await response.json();
  const userClaims = payload[0]?.user_claims || [];
  const objectIdClaim = userClaims.find(
    (claim: any) =>
      claim.typ === "http://schemas.microsoft.com/identity/claims/objectidentifier"
  );
  const userId = objectIdClaim?.val;
  if (userId) {
    localStorage.setItem("userId", userId);
  }
  return payload;
}

function getUserIdFromLocalStorage(): string | null {
  return localStorage.getItem("userId");
}

export const historyRead = async (convId: string): Promise<ChatMessage[]> => {
  const userId = getUserIdFromLocalStorage();
  const endpoint = `/historyfab/read?id=${encodeURIComponent(convId)}`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
    });

    console.log(response.status, response.statusText);
    
    if (!response.ok) {
      // Use new error handling system
      await ApiErrorHandler.handleApiError(response, endpoint);
      
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
    // Use new error handling system
    ApiErrorHandler.handleNetworkError(error, endpoint);
    return [];
  }
};

export const historyList = async (
  offset = 0,
  limit = 25
): Promise<Conversation[] | null> => {
  const userId = getUserIdFromLocalStorage();
  const endpoint = `/historyfab/list?offset=${offset}&limit=${limit}`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
    });

    if (!response.ok) {
      // Use new error handling system
      await ApiErrorHandler.handleApiError(response, endpoint);
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
  messages: ChatMessage[],
  convId: string
): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const endpoint = `/historyfab/update`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "POST",
      body: JSON.stringify({
        conversation_id: convId,
        messages: messages,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
    });

    // Log errors but still return the response (maintaining current behavior)
    if (!response.ok) {
      await ApiErrorHandler.handleApiError(response, endpoint);
    }
    
    return response;
    
  } catch (error) {
    // Use new error handling system
    ApiErrorHandler.handleNetworkError(error, endpoint);
    
    // Return error response (maintaining current behavior)
    const errRes: Response = {
      ...new Response(),
      ok: false,
      status: 500,
    };
    return errRes;
  }
};

export async function callConversationApi(
  options: ConversationRequest,
  abortSignal: AbortSignal
): Promise<Response> {
  const userId = getUserIdFromLocalStorage();
  const endpoint = `/api/chat`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
      body: JSON.stringify({
        messages: options.messages,
        conversation_id: options.id,
        last_rag_response: options.last_rag_response
      }),
      signal: abortSignal,
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
  const userId = getUserIdFromLocalStorage();
  const endpoint = `/historyfab/rename`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "POST",
      body: JSON.stringify({
        conversation_id: convId,
        title: title,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
    });

    // Log errors but still return the response (maintaining current behavior)
    if (!response.ok) {
      await ApiErrorHandler.handleApiError(response, endpoint);
    }
    
    return response;
    
  } catch (error) {
    console.error("Error renaming conversation:", error);
    // Use new error handling system
    ApiErrorHandler.handleNetworkError(error, endpoint);
    
    // Return error response (maintaining current behavior)
    const errRes: Response = {
      ...new Response(),
      ok: false,
      status: 500,
    };
    return errRes;
  }
};

export const historyDelete = async (convId: string): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();  
  const endpoint = `/historyfab/delete?id=${encodeURIComponent(convId)}`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
    });

    // Log errors but still return the response (maintaining current behavior)
    if (!response.ok) {
      await ApiErrorHandler.handleApiError(response, endpoint);
    }
    
    return response;
    
  } catch (error) {
    // Use new error handling system
    ApiErrorHandler.handleNetworkError(error, endpoint);
    
    // Return error response (maintaining current behavior)
    const errRes: Response = {
      ...new Response(),
      ok: false,
      status: 500,
    };
    return errRes;
  }
};

export const historyDeleteAll = async (): Promise<Response> => {
  const userId = getUserIdFromLocalStorage();
  const endpoint = `/historyfab/delete_all`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      method: "DELETE",
      body: JSON.stringify({}),
      headers: {
        "Content-Type": "application/json",
        "X-Ms-Client-Principal-Id": userId || "",
      },
    });

    // Log errors but still return the response (maintaining current behavior)
    if (!response.ok) {
      await ApiErrorHandler.handleApiError(response, endpoint);
    }
    
    return response;
    
  } catch (error) {
    // Use new error handling system
    ApiErrorHandler.handleNetworkError(error, endpoint);
    
    // Return error response (maintaining current behavior)
    const errRes: Response = {
      ...new Response(),
      ok: false,
      status: 500,
    };
    return errRes;
  }
};

export const fetchCitationContent = async (body: any) => {
  const endpoint = `/api/fetch-azure-search-content`;
  
  try {
    const response = await fetch(`${baseURL}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(body),
    });
    
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
