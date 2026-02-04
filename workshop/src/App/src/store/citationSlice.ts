import { createSlice, createAsyncThunk, type PayloadAction } from "@reduxjs/toolkit";
import { fetchCitationContent as fetchCitationContentApi } from "../api/api";
import type { Citation } from "../types/AppTypes";

export interface CitationState {
  activeCitation?: any;
  showCitation: boolean;
  currentConversationIdForCitation?: string;
  loadingCitation: boolean;
}

const initialState: CitationState = {
  activeCitation: null,
  showCitation: false,
  currentConversationIdForCitation: "",
  loadingCitation: false,
};

// Async thunks
export const fetchCitationContent = createAsyncThunk(
  'citation/fetchCitationContent',
  async ({ citation, conversationId }: { citation: Citation; conversationId: string }) => {
    const citationContent = await fetchCitationContentApi(citation);
    return { citation, content: citationContent.content, conversationId };
  }
);

const citationSlice = createSlice({
  name: "citation",
  initialState,
  reducers: {
    setCitation: (
      state,
      action: PayloadAction<{
        activeCitation?: any;
        showCitation: boolean;
        currentConversationIdForCitation?: string;
      }>
    ) => {
      state.activeCitation = action.payload.activeCitation || state.activeCitation;
      state.showCitation = action.payload.showCitation;
      state.currentConversationIdForCitation =
        action.payload?.currentConversationIdForCitation || state.currentConversationIdForCitation;
    },
    clearCitation: (state) => {
      state.activeCitation = null;
      state.showCitation = false;
      state.currentConversationIdForCitation = "";
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCitationContent.pending, (state) => {
        state.loadingCitation = true;
      })
      .addCase(fetchCitationContent.fulfilled, (state, action) => {
        state.activeCitation = { ...action.payload.citation, content: action.payload.content };
        state.showCitation = true;
        state.currentConversationIdForCitation = action.payload.conversationId;
        state.loadingCitation = false;
      })
      .addCase(fetchCitationContent.rejected, (state) => {
        state.loadingCitation = false;
      });
  },
});

export const { setCitation, clearCitation } = citationSlice.actions;

export default citationSlice.reducer;
