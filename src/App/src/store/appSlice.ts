import { createSlice, createAsyncThunk, type PayloadAction } from "@reduxjs/toolkit";
import type { AppConfig, ChartConfigItem, CosmosDBHealth } from "../types/AppTypes";
import { generateUUIDv4 } from "../configs/Utils";
import { getUserInfo as getUserInfoApi, type UserInfo } from "../api/api";

export interface AppState {
  selectedConversationId: string;
  generatedConversationId: string;
  config: {
    appConfig: AppConfig;
    charts: ChartConfigItem[];
  };
  cosmosInfo: CosmosDBHealth;
  showAppSpinner: boolean;
  userInfo: UserInfo[];
  loadingUserInfo: boolean;
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
  userInfo: [],
  loadingUserInfo: false,
};

// Async thunks
export const fetchUserInfo = createAsyncThunk(
  'app/fetchUserInfo',
  async () => {
    const userInfoList = await getUserInfoApi();
    return userInfoList;
  }
);

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
  extraReducers: (builder) => {
    builder
      .addCase(fetchUserInfo.pending, (state) => {
        state.loadingUserInfo = true;
      })
      .addCase(fetchUserInfo.fulfilled, (state, action) => {
        state.userInfo = action.payload;
        state.loadingUserInfo = false;
      })
      .addCase(fetchUserInfo.rejected, (state) => {
        state.loadingUserInfo = false;
      });
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
