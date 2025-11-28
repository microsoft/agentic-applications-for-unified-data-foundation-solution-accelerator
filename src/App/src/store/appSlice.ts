import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { AppConfig, ChartConfigItem, CosmosDBHealth } from "../types/AppTypes";
import { generateUUIDv4 } from "../configs/Utils";

export interface AppState {
  selectedConversationId: string;
  generatedConversationId: string;
  config: {
    appConfig: AppConfig;
    charts: ChartConfigItem[];
  };
  cosmosInfo: CosmosDBHealth;
  showAppSpinner: boolean;
}

const initialState: AppState = {
  selectedConversationId: "",
  generatedConversationId: generateUUIDv4(),
  config: {
    appConfig: null,
    charts: [],
  },
  cosmosInfo: { cosmosDB: false, status: "" },
  showAppSpinner: false,
};

const appSlice = createSlice({
  name: "app",
  initialState,
  reducers: {
    setSelectedConversationId: (state, action: PayloadAction<string>) => {
      state.selectedConversationId = action.payload;
    },
    generateNewConversationId: (state) => {
      state.generatedConversationId = generateUUIDv4();
    },
    startNewConversation: (state) => {
      state.selectedConversationId = "";
      state.generatedConversationId = generateUUIDv4();
    },
    saveConfig: (state, action: PayloadAction<AppState["config"]>) => {
      state.config = { ...state.config, ...action.payload };
    },
    setCosmosInfo: (state, action: PayloadAction<CosmosDBHealth>) => {
      state.cosmosInfo = action.payload;
    },
    setAppSpinner: (state, action: PayloadAction<boolean>) => {
      state.showAppSpinner = action.payload;
    },
  },
});

export const {
  setSelectedConversationId,
  generateNewConversationId,
  startNewConversation,
  saveConfig,
  setCosmosInfo,
  setAppSpinner,
} = appSlice.actions;

export default appSlice.reducer;
