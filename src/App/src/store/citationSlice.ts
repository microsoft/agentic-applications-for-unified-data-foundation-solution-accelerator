import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface CitationState {
  activeCitation?: any;
  showCitation: boolean;
  currentConversationIdForCitation?: string;
}

const initialState: CitationState = {
  activeCitation: null,
  showCitation: false,
  currentConversationIdForCitation: "",
};

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
});

export const { setCitation, clearCitation } = citationSlice.actions;

export default citationSlice.reducer;
