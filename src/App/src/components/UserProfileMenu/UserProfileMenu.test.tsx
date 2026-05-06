import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import appReducer from "../../store/appSlice";
import chatReducer from "../../store/chatSlice";
import chatHistoryReducer from "../../store/chatHistorySlice";
import citationReducer from "../../store/citationSlice";

// Mock the config module (used by api.ts and App.tsx)
jest.mock("../../config", () => ({
  getApiBaseUrl: () => "http://localhost:8000",
  getChatLandingText: () => "Test landing text",
  isWorkShopDeployment: () => false,
  getAppTitlePrimary: () => "Test App",
  getAppTitleSecondary: () => "Subtitle",
}));

// Mock the api module
const mockGetUserInfo = jest.fn();
jest.mock("../../api/api", () => ({
  getUserInfo: (...args: any[]) => mockGetUserInfo(...args),
  getAppConfig: jest.fn().mockResolvedValue({ appConfig: null, charts: [] }),
  getCosmosDBHealth: jest.fn().mockResolvedValue({ cosmosDB: false, status: "" }),
}));

// Mock child components to isolate the header/menu tests
jest.mock("../../components/Chat/Chat", () => () => <div data-testid="mock-chat" />);
jest.mock("../../components/ChatHistoryPanel/ChatHistoryPanel", () => ({
  ChatHistoryPanel: () => <div data-testid="mock-chat-history" />,
}));
jest.mock("../../components/CustomSpinner/CustomSpinner", () => () => null);
jest.mock("../../components/CitationPanel/CitationPanel", () => () => null);
jest.mock("../../components/Svg/Svg", () => ({
  AppLogo: () => <div data-testid="app-logo" />,
}));

// Import Dashboard after mocking dependencies
import Dashboard from "../../App";

function createTestStore() {
  return configureStore({
    reducer: {
      chat: chatReducer,
      chatHistory: chatHistoryReducer,
      citation: citationReducer,
      app: appReducer,
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const store = createTestStore();
  return render(<Provider store={store}>{ui}</Provider>);
}

const mockUserInfo = [
  {
    access_token: "mock-token",
    expires_on: "2026-12-31",
    id_token: "mock-id-token",
    provider_name: "aad",
    user_claims: [
      { typ: "name", val: "Test User" },
      { typ: "preferred_username", val: "testuser@example.com" },
      {
        typ: "http://schemas.microsoft.com/identity/claims/objectidentifier",
        val: "user-obj-id-123",
      },
    ],
    user_id: "testuser@example.com",
  },
];

describe("User Profile Menu", () => {
  const originalLocation = window.location;

  beforeEach(() => {
    // Mock window.location for logout test
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...originalLocation, href: "", origin: "http://localhost:3000" },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
    mockGetUserInfo.mockReset();
  });

  it("shows a neutral avatar when user is not authenticated", async () => {
    mockGetUserInfo.mockResolvedValue([]);

    renderWithProviders(<Dashboard />);

    // Should show a generic avatar (no menu trigger)
    const avatar = await screen.findByRole("img", { hidden: true });
    expect(avatar).toBeInTheDocument();

    // Should NOT show Sign out option
    expect(screen.queryByText("Sign out")).not.toBeInTheDocument();
  });

  it("shows user profile menu when authenticated", async () => {
    mockGetUserInfo.mockResolvedValue(mockUserInfo);

    renderWithProviders(<Dashboard />);

    // Wait for the avatar button to appear with user's name
    const menuButton = await screen.findByRole("button", {
      name: /Signed in as Test User/i,
    });
    expect(menuButton).toBeInTheDocument();
  });

  it("displays user name and email in the dropdown menu", async () => {
    mockGetUserInfo.mockResolvedValue(mockUserInfo);

    renderWithProviders(<Dashboard />);

    // Open the menu
    const menuButton = await screen.findByRole("button", {
      name: /Signed in as Test User/i,
    });
    fireEvent.click(menuButton);

    // Check name and email appear in the dropdown
    expect(await screen.findByText("Test User")).toBeInTheDocument();
    expect(screen.getByText("testuser@example.com")).toBeInTheDocument();
  });

  it("clicking Sign out redirects to EasyAuth logout with post_logout_redirect_uri", async () => {
    mockGetUserInfo.mockResolvedValue(mockUserInfo);

    renderWithProviders(<Dashboard />);

    // Open the menu
    const menuButton = await screen.findByRole("button", {
      name: /Signed in as Test User/i,
    });
    fireEvent.click(menuButton);

    // Click Sign out
    const signOutItem = await screen.findByText("Sign out");
    fireEvent.click(signOutItem);

    // Verify redirect URL includes post_logout_redirect_uri
    expect(window.location.href).toBe(
      "/.auth/logout?post_logout_redirect_uri=" +
        encodeURIComponent("http://localhost:3000")
    );
  });

  it("shows menu with fallback 'User' label when authenticated but name claim is missing", async () => {
    const userInfoNoName = [
      {
        ...mockUserInfo[0],
        user_claims: [
          { typ: "preferred_username", val: "noname@example.com" },
          {
            typ: "http://schemas.microsoft.com/identity/claims/objectidentifier",
            val: "user-obj-id-456",
          },
        ],
      },
    ];
    mockGetUserInfo.mockResolvedValue(userInfoNoName);

    renderWithProviders(<Dashboard />);

    // Should still show the menu button (authenticated)
    const menuButton = await screen.findByRole("button", {
      name: /User menu/i,
    });
    fireEvent.click(menuButton);

    // Should show "User" as fallback and still show Sign out
    expect(await screen.findByText("User")).toBeInTheDocument();
    expect(screen.getByText("Sign out")).toBeInTheDocument();
  });
});
