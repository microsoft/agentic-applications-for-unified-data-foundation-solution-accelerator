import React, { useEffect, useState, useRef } from "react";
import Chat from "./components/Chat/Chat";
import {
  FluentProvider,
  Subtitle2,
  Body2,
  webLightTheme,
  Avatar,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  MenuDivider,
  Button,
} from "@fluentui/react-components";
import { SignOut24Regular, Person24Regular } from "@fluentui/react-icons";
import "./App.css";
import { ChatHistoryPanel } from "./components/ChatHistoryPanel/ChatHistoryPanel";


import { useAppDispatch, useAppSelector } from "./store/hooks";
import {
  fetchChatHistory, // eslint-disable-line @typescript-eslint/no-unused-vars
  fetchConversationMessages, // eslint-disable-line @typescript-eslint/no-unused-vars
  deleteAllConversations,
} from "./store/chatHistorySlice";
import { setSelectedConversationId, startNewConversation, fetchUserInfo } from "./store/appSlice";
import { clearCitation } from "./store/citationSlice";
import { setMessages, clearChat } from "./store/chatSlice";
import { AppLogo } from "./components/Svg/Svg";
import CustomSpinner from "./components/CustomSpinner/CustomSpinner";
import CitationPanel from "./components/CitationPanel/CitationPanel";
import { getAppTitlePrimary, getAppTitleSecondary } from "./config";
const panels = {
  CHAT: "CHAT",
  CHATHISTORY: "CHATHISTORY",
};

const defaultSingleColumnConfig: Record<string, number> = {
  [panels.CHAT]: 100,
  [panels.CHATHISTORY]: 30,
};

const defaultPanelShowStates = {
  [panels.CHAT]: true,
  [panels.CHATHISTORY]: false,
};

const Dashboard: React.FC = () => {
  const dispatch = useAppDispatch();
  const { appConfig } = useAppSelector((state) => state.app.config);
  const showAppSpinner = useAppSelector((state) => state.app.showAppSpinner);
  const citation = useAppSelector((state) => state.citation);

  const [panelShowStates, setPanelShowStates] = useState<
    Record<string, boolean>
  >({ ...defaultPanelShowStates });
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>({
    ...defaultSingleColumnConfig,
  });
  const [showClearAllConfirmationDialog, setChowClearAllConfirmationDialog] =
    useState(false);
  const [clearing, setClearing] = React.useState(false);
  const [clearingError, setClearingError] = React.useState(false);
  const [isInitialAPItriggered, setIsInitialAPItriggered] = useState(false);
  const [offset, setOffset] = useState<number>(0);
  const OFFSET_INCREMENT = 25;
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [name, setName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const isInitialFetchStarted = useRef(false);

  useEffect(() => {
    dispatch(fetchUserInfo()).unwrap().then((res) => {
      if (res[0]) {
        setIsAuthenticated(true);
        const name: string = res[0]?.user_claims?.find((claim: any) => claim.typ === 'name')?.val ?? ''
        const email: string = res[0]?.user_claims?.find((claim: any) => claim.typ === 'preferred_username' || claim.typ === 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress')?.val ?? ''
        setName(name)
        setEmail(email)
      }
    }).catch(() => {
      // Error fetching user info - silent fail
    })
  }, []);

  const updateLayoutWidths = (newState: Record<string, boolean>) => {
    const noOfWidgetsOpen = Object.values(newState).filter((val) => val).length;
    if (appConfig === null) {
      return;
    }

    if (
      noOfWidgetsOpen === 1 ||
      (noOfWidgetsOpen === 2 && !newState[panels.CHAT])
    ) {
      setPanelWidths(defaultSingleColumnConfig);
    } else if (noOfWidgetsOpen === 2 && newState[panels.CHAT]) {
      const panelsInOpenState = Object.keys(newState).filter(
        (key) => newState[key]
      );
      const twoColLayouts = Object.keys(appConfig.TWO_COLUMN) as string[];
      for (let i = 0; i < twoColLayouts.length; i++) {
        const key = twoColLayouts[i] as string;
        const panelNames = key.split("_");
        const isMatched = panelsInOpenState.every((val) =>
          panelNames.includes(val)
        );
        const TWO_COLUMN = appConfig.TWO_COLUMN as Record<
          string,
          Record<string, number>
        >;
        if (isMatched) {
          setPanelWidths({ ...TWO_COLUMN[key] });
          break;
        }
      }
    } 
  };

  useEffect(() => {
    updateLayoutWidths(panelShowStates);
  }, [appConfig]);

  const onHandlePanelStates = (panelName: string) => {
    if (panelName !== panels.CHATHISTORY) {
      dispatch(clearCitation());
    }
    const newState = {
      ...panelShowStates,
      [panelName]: !panelShowStates[panelName],
    };
    updateLayoutWidths(newState);
    setPanelShowStates(newState);
  };

  const getHistoryListData = async () => {
    if (!hasMoreRecords) {
      return;
    }
    isInitialFetchStarted.current = true;
    const result = await dispatch(fetchChatHistory(offset));
    if (result.payload) {
      const payload = result.payload as { conversations: any[] | null; offset: number };
      const conversations = payload.conversations;
      if (conversations && conversations.length === OFFSET_INCREMENT) {
        setOffset((offset) => (offset += OFFSET_INCREMENT));
        // Stopping offset increment if there were no records
      } else if (conversations && conversations.length < OFFSET_INCREMENT) {
        setHasMoreRecords(false);
      }
    }
  };

  const onClearAllChatHistory = async () => {
    setChowClearAllConfirmationDialog(false);
    dispatch(clearCitation());
    setClearing(true);
    try {
      await dispatch(deleteAllConversations()).unwrap();
      
      dispatch(startNewConversation());
      dispatch(clearChat());
      setOffset(0);
      setHasMoreRecords(true);
    } catch {
      setClearingError(true);
    }
    setClearing(false);
  };

  useEffect(() => {
    setIsInitialAPItriggered(true);
  }, []);

  useEffect(() => {
    if (isInitialAPItriggered && !isInitialFetchStarted.current) {
      (async () => {
        getHistoryListData();
      })();
    }
  }, [isInitialAPItriggered]);

  const onSelectConversation = async (id: string) => {
    if (!id) return;
    dispatch(setSelectedConversationId(id));

    try {
      const result = await dispatch(fetchConversationMessages(id)).unwrap();
      if (result && result.messages) {
        dispatch(setMessages(result.messages));
      }
    } catch {
      // Error fetching conversation messages
    }
  };

  const onClickClearAllOption = () => {
    setChowClearAllConfirmationDialog((prevFlag) => !prevFlag);
  };

  const onHideClearAllDialog = () => {
    setChowClearAllConfirmationDialog((prevFlag) => !prevFlag);
    setTimeout(() => {
      setClearingError(false);
    }, 1000);
  };

  const handleLogout = () => {
    localStorage.removeItem("userId");
    sessionStorage.removeItem("accessToken");
    window.location.href = "/.auth/logout?post_logout_redirect_uri=" + encodeURIComponent(window.location.origin);
  };

  const getUserInitials = (fullName: string | undefined): string => {
    if (!fullName) return "U";
    const cleanName = fullName.replace(/\s*\([^)]*\)/g, "").trim();
    if (!cleanName) return "U";
    const parts = cleanName.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return cleanName.charAt(0).toUpperCase();
  };

  const displayName = name || "User";

  return (
    <FluentProvider
      theme={webLightTheme}
      style={{ height: "100%", backgroundColor: "#F5F5F5" }}
    >
      <CustomSpinner loading={showAppSpinner} label="Please wait.....!" />
      <div className="header">
        <div className="header-left-section">
          <AppLogo />
          <Subtitle2>
            {getAppTitlePrimary()} <Body2 style={{ gap: "10px" }}>{getAppTitleSecondary()}</Body2>
          </Subtitle2>
        </div>
        <div className="header-right-section">
          {isAuthenticated ? (
            <Menu>
              <MenuTrigger disableButtonEnhancement>
                <Button
                  appearance="subtle"
                  style={{ minWidth: "auto", padding: "4px" }}
                  title={name ? `Signed in as ${name}` : "User menu"}
                  aria-label={name ? `User menu for ${name}` : "User menu"}
                  icon={
                    <Avatar
                      name={displayName}
                      initials={getUserInitials(name)}
                      icon={!name ? <Person24Regular /> : undefined}
                      size={28}
                      color={name ? "colorful" : "neutral"}
                      style={{ fontWeight: "bold" }}
                    />
                  }
                />
              </MenuTrigger>
              <MenuPopover>
                <MenuList>
                  <MenuItem icon={<Person24Regular />} disabled>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", maxWidth: 260, minWidth: 0 }}>
                      <span
                        style={{
                          fontWeight: 600,
                          fontSize: "13px",
                          maxWidth: "100%",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                        title={name || "User"}
                      >
                        {name || "User"}
                      </span>
                      {email && (
                        <span
                          style={{
                            fontSize: "11px",
                            color: "#616161",
                            maxWidth: "100%",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                          title={email}
                        >
                          {email}
                        </span>
                      )}
                    </div>
                  </MenuItem>
                  <MenuDivider />
                  <MenuItem icon={<SignOut24Regular />} onClick={handleLogout}>
                    Sign out
                  </MenuItem>
                </MenuList>
              </MenuPopover>
            </Menu>
          ) : (
            <Avatar icon={<Person24Regular />} size={28} color="neutral" />
          )}
        </div>
      </div>
      <div className="main-container">
        {/* LEFT PANEL:  CHAT */}
        {panelShowStates?.[panels.CHAT] && (
          <div
            style={{
              width: `${panelWidths[panels.CHAT]}%`,
            }}
          >
            <Chat
              onHandlePanelStates={onHandlePanelStates}
              panels={panels}
              panelShowStates={panelShowStates}
            />
          </div>
        )}
        {citation.showCitation && citation.currentConversationIdForCitation !== "" && (
          <div
            style={{
              // width: `${panelWidths[panels.DASHBOARD]}%`,
              width: `${panelWidths[panels.CHATHISTORY] || 17}%`,
              // minWidth: '30%'
            }}
          >
            <CitationPanel activeCitation={citation.activeCitation}  />

          </div>
        )}
        {/* RIGHT PANEL: CHAT HISTORY */}
        {panelShowStates?.[panels.CHAT] &&
          panelShowStates?.[panels.CHATHISTORY] && (
            <div
              style={{
                width: `${panelWidths[panels.CHATHISTORY]}%`,
              }}
            >
              <ChatHistoryPanel
                clearing={clearing}
                clearingError={clearingError}
                handleFetchHistory={() => getHistoryListData()}
                onClearAllChatHistory={onClearAllChatHistory}
                onClickClearAllOption={onClickClearAllOption}
                onHideClearAllDialog={onHideClearAllDialog}
                onSelectConversation={onSelectConversation}
                showClearAllConfirmationDialog={showClearAllConfirmationDialog}
              />
              {/* {useAppContext?.state.isChatHistoryOpen &&
            useAppContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && <ChatHistoryPanel />} */}
            </div>
          )}
      </div>
    </FluentProvider>
  );
};

export default Dashboard;
