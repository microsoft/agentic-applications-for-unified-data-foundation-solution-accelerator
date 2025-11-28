import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { ChatMessage } from "../types/AppTypes";

export interface ChatState {
  generatingResponse: boolean;
  messages: ChatMessage[];
  userMessage: string;
  isStreamingInProgress: boolean;
  citations: string | null;
}

const initialState: ChatState = {
  generatingResponse: false,
  messages: [],
  userMessage: "",
  citations: "",
  isStreamingInProgress: false,
};

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    setUserMessage: (state, action: PayloadAction<string>) => {
      state.userMessage = action.payload;
    },
    setGeneratingResponse: (state, action: PayloadAction<boolean>) => {
      state.generatingResponse = action.payload;
    },
    addMessages: (state, action: PayloadAction<ChatMessage[]>) => {
      state.messages.push(...action.payload);
    },
    setMessages: (state, action: PayloadAction<ChatMessage[]>) => {
      state.messages = action.payload;
    },
    updateMessageById: (state, action: PayloadAction<ChatMessage>) => {
      const messageID = action.payload.id;
      const matchIndex = state.messages.findIndex(
        (obj) => String(obj.id) === String(messageID)
      );
      if (matchIndex > -1) {
        state.messages[matchIndex] = action.payload;
      } else {
        state.messages.push(action.payload);
      }
      state.citations = "";
      state.isStreamingInProgress = true;
    },
    setStreamingFlag: (state, action: PayloadAction<boolean>) => {
      state.isStreamingInProgress = action.payload;
    },
    clearChat: (state) => {
      state.messages = [];
      state.userMessage = "";
      state.citations = "";
      state.isStreamingInProgress = false;
    },
  },
});

export const {
  setUserMessage,
  setGeneratingResponse,
  addMessages,
  setMessages,
  updateMessageById,
  setStreamingFlag,
  clearChat,
} = chatSlice.actions;

export default chatSlice.reducer;
