import { createSlice, createAsyncThunk, type PayloadAction } from "@reduxjs/toolkit";
import type { Conversation, ChatMessage } from "../types/AppTypes";
import { historyList, historyRead, historyDeleteAll, historyDelete, historyUpdate, historyRename } from "../api/api";

export interface ChatHistoryState {
  list: Conversation[];
  fetchingConversations: boolean;
  isFetchingConvMessages: boolean;
  isHistoryUpdateAPIPending: boolean;
}

const initialState: ChatHistoryState = {
  list: [],
  fetchingConversations: false,
  isFetchingConvMessages: false,
  isHistoryUpdateAPIPending: false,
};

// Async Thunks
export const fetchChatHistory = createAsyncThunk(
  "chatHistory/fetchList",
  async () => {
    const response = await historyList();
    return response;
  }
);

export const fetchConversationMessages = createAsyncThunk(
  "chatHistory/fetchConversation",
  async (conversationId: string) => {
    const response = await historyRead(conversationId);
    return { conversationId, messages: response };
  }
);

export const deleteAllConversations = createAsyncThunk(
  "chatHistory/deleteAll",
  async () => {
    await historyDeleteAll();
    return null;
  }
);

export const deleteConversation = createAsyncThunk(
  "chatHistory/deleteOne",
  async (conversationId: string) => {
    await historyDelete(conversationId);
    return conversationId;
  }
);

export const updateConversation = createAsyncThunk(
  "chatHistory/update",
  async ({ conversationId, messages }: { conversationId: string; messages: ChatMessage[] }) => {
    await historyUpdate(messages, conversationId);
    return { conversationId, messages };
  }
);

export const renameConversation = createAsyncThunk(
  "chatHistory/rename",
  async ({ conversationId, newTitle }: { conversationId: string; newTitle: string }) => {
    await historyRename(conversationId, newTitle);
    return { conversationId, newTitle };
  }
);

const chatHistorySlice = createSlice({
  name: "chatHistory",
  initialState,
  reducers: {
    addConversations: (state, action: PayloadAction<Conversation[]>) => {
      state.list.push(...action.payload);
    },
    addNewConversation: (state, action: PayloadAction<Conversation>) => {
      state.list.unshift(action.payload);
    },
    updateConversationTitle: (state, action: PayloadAction<{ id: string; newTitle: string }>) => {
      const index = state.list.findIndex((obj) => obj.id === action.payload.id);
      if (index > -1) {
        state.list[index].title = action.payload.newTitle;
      }
    },
    showConversationMessages: (state, action: PayloadAction<{ id: string; messages: ChatMessage[] }>) => {
      const matchedIndex = state.list.findIndex((obj) => obj.id === action.payload.id);
      if (matchedIndex > -1) {
        state.list[matchedIndex].messages = action.payload.messages;
      }
    },
    setFetchingConversations: (state, action: PayloadAction<boolean>) => {
      state.fetchingConversations = action.payload;
    },
    setFetchingConvMessages: (state, action: PayloadAction<boolean>) => {
      state.isFetchingConvMessages = action.payload;
    },
    setHistoryUpdateAPIPending: (state, action: PayloadAction<boolean>) => {
      state.isHistoryUpdateAPIPending = action.payload;
    },
    clearAll: (state) => {
      state.list = [];
    },
  },
  extraReducers: (builder) => {
    // Fetch Chat History
    builder.addCase(fetchChatHistory.pending, (state) => {
      state.fetchingConversations = true;
    });
    builder.addCase(fetchChatHistory.fulfilled, (state, action) => {
      state.list = action.payload || [];
      state.fetchingConversations = false;
    });
    builder.addCase(fetchChatHistory.rejected, (state) => {
      state.fetchingConversations = false;
    });

    // Fetch Conversation Messages
    builder.addCase(fetchConversationMessages.pending, (state) => {
      state.isFetchingConvMessages = true;
    });
    builder.addCase(fetchConversationMessages.fulfilled, (state, action) => {
      const { conversationId, messages } = action.payload;
      const matchedIndex = state.list.findIndex((obj) => obj.id === conversationId);
      if (matchedIndex > -1) {
        state.list[matchedIndex].messages = messages;
      }
      state.isFetchingConvMessages = false;
    });
    builder.addCase(fetchConversationMessages.rejected, (state) => {
      state.isFetchingConvMessages = false;
    });

    // Delete All Conversations
    builder.addCase(deleteAllConversations.fulfilled, (state) => {
      state.list = [];
    });

    // Delete Single Conversation
    builder.addCase(deleteConversation.fulfilled, (state, action) => {
      state.list = state.list.filter((conversation) => conversation.id !== action.payload);
    });

    // Update Conversation
    builder.addCase(updateConversation.pending, (state) => {
      state.isHistoryUpdateAPIPending = true;
    });
    builder.addCase(updateConversation.fulfilled, (state) => {
      state.isHistoryUpdateAPIPending = false;
    });
    builder.addCase(updateConversation.rejected, (state) => {
      state.isHistoryUpdateAPIPending = false;
    });

    // Rename Conversation
    builder.addCase(renameConversation.fulfilled, (state, action) => {
      const { conversationId, newTitle } = action.payload;
      const index = state.list.findIndex((obj) => obj.id === conversationId);
      if (index > -1) {
        state.list[index].title = newTitle;
      }
    });
  },
});

export const {
  addConversations,
  addNewConversation,
  updateConversationTitle,
  showConversationMessages,
  setFetchingConversations,
  setFetchingConvMessages,
  setHistoryUpdateAPIPending,
  clearAll,
} = chatHistorySlice.actions;

export default chatHistorySlice.reducer;
