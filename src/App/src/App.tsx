import React, { useEffect, useState } from "react";
import Chat from "./components/Chat/Chat";
import {
  FluentProvider,
  Subtitle2,
  Body2,
  webLightTheme,
  Avatar,
} from "@fluentui/react-components";
import "./App.css";
import { ChatHistoryPanel } from "./components/ChatHistoryPanel/ChatHistoryPanel";

import {
  getUserInfo,
  historyDeleteAll,
  historyList,
  historyRead,
} from "./api/api";

import { useAppDispatch, useAppSelector } from "./store/hooks";
import {
  fetchChatHistory,
  fetchConversationMessages,
  setFetchingConversations,
  addConversations,
  clearAll,
  setFetchingConvMessages,
  showConversationMessages,
} from "./store/chatHistorySlice";
import { setSelectedConversationId, setAppSpinner, startNewConversation } from "./store/appSlice";
import { setCitation, clearCitation } from "./store/citationSlice";
import { setMessages, clearChat } from "./store/chatSlice";
import { ChatMessage } from "./types/AppTypes";
import { AppLogo } from "./components/Svg/Svg";
import CustomSpinner from "./components/CustomSpinner/CustomSpinner";
import CitationPanel from "./components/CitationPanel/CitationPanel";
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
  const chatHistory = useAppSelector((state) => state.chatHistory);
  
  const [panelShowStates, setPanelShowStates] = useState<
    Record<string, boolean>
  >({ ...defaultPanelShowStates });
  const [panelWidths, setPanelWidths] = useState<Record<string, number>>({
    ...defaultSingleColumnConfig,
  });
  const [layoutWidthUpdated, setLayoutWidthUpdated] = useState<boolean>(false);
  const [showClearAllConfirmationDialog, setChowClearAllConfirmationDialog] =
    useState(false);
  const [clearing, setClearing] = React.useState(false);
  const [clearingError, setClearingError] = React.useState(false);
  const [isInitialAPItriggered, setIsInitialAPItriggered] = useState(false);
  const [showAuthMessage, setShowAuthMessage] = useState<boolean | undefined>();
  const [offset, setOffset] = useState<number>(0);
  const OFFSET_INCREMENT = 25;
  const [hasMoreRecords, setHasMoreRecords] = useState<boolean>(true);
  const [name, setName] = useState<string>("");


  const getUserInfoList = async () => {
    const userInfoList = await getUserInfo();
    if (
      userInfoList.length === 0 &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1"
    ) {
      setShowAuthMessage(true);
    } else {
      setShowAuthMessage(false);
    }
  };

  useEffect(() => {
    getUserInfoList();
  }, []);

  useEffect(() => {
    getUserInfo().then((res) => {
      const name: string = res[0]?.user_claims?.find((claim: any) => claim.typ === 'name')?.val ?? ''
      setName(name)
    }).catch(() => {
      // Error fetching user info - silent fail
    })
  }, [])

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
    dispatch(clearCitation());
    setLayoutWidthUpdated((prevFlag) => !prevFlag);
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
    dispatch(setFetchingConversations(true));
    const convs = await historyList(offset);
    if (convs !== null) {
      if (convs.length === OFFSET_INCREMENT) {
        setOffset((offset) => (offset += OFFSET_INCREMENT));
        // Stopping offset increment if there were no records
      } else if (convs.length < OFFSET_INCREMENT) {
        setHasMoreRecords(false);
      }
      dispatch(addConversations(convs));
    }
    dispatch(setFetchingConversations(false));
  };

  const onClearAllChatHistory = async () => {
    dispatch(setAppSpinner(true));
    dispatch(clearCitation());
    setClearing(true);
    const response = await historyDeleteAll();
    if (!response.ok) {
      setClearingError(true);
    } else {
      setChowClearAllConfirmationDialog(false);
      dispatch(startNewConversation());
      dispatch(clearChat());
      dispatch(clearAll());
    }
    setClearing(false);
    dispatch(setAppSpinner(false));
  };

  useEffect(() => {
    setIsInitialAPItriggered(true);
  }, []);

  useEffect(() => {
    if (isInitialAPItriggered) {
      (async () => {
        getHistoryListData();
      })();
    }
  }, [isInitialAPItriggered]);

  const [ASSISTANT, TOOL, ERROR, USER] = ["assistant", "tool", "error", "user"];



  const onSelectConversation = async (id: string) => {
    if (!id) return;
    dispatch(setFetchingConvMessages(true));
    dispatch(setSelectedConversationId(id));

    try {
      const responseMessages = await historyRead(id);

      if (responseMessages) {
        dispatch(showConversationMessages({
          id,
          messages: responseMessages,
        }));
        dispatch(setMessages(responseMessages));
      }

    } catch {
      // Error fetching conversation messages
    } finally {
      dispatch(setFetchingConvMessages(false));
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
            Contoso <Body2 style={{ gap: "10px" }}>| Unified Data Analysis Agents</Body2>
          </Subtitle2>
        </div>
        <div className="header-right-section">
          <div>
            <Avatar name={name} title={name} />
          </div>
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
