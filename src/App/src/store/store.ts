import { configureStore } from "@reduxjs/toolkit";
import chatReducer from "./chatSlice";
import chatHistoryReducer from "./chatHistorySlice";
import citationReducer from "./citationSlice";
import appReducer from "./appSlice";

export const store = configureStore({
  reducer: {
    chat: chatReducer,
    chatHistory: chatHistoryReducer,
    citation: citationReducer,
    app: appReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types if needed
        ignoredActions: [],
        // Ignore these field paths in all actions
        ignoredActionPaths: [],
        // Ignore these paths in the state
        ignoredPaths: [],
      },
    }),
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
