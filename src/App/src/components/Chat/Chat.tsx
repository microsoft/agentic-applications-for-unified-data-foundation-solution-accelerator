import React, { useEffect, useRef, useState, useCallback, useMemo } from "react";
import {
  Button,
  Textarea,
  Subtitle2,
  Body1,
} from "@fluentui/react-components";
import "./Chat.css";
import { DefaultButton, Spinner, SpinnerSize } from "@fluentui/react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import {
  setUserMessage as setUserMessageAction,
  setGeneratingResponse,
  addMessages,
  updateMessageById,
  setStreamingFlag,
  clearChat,
  sendMessage,
} from "../../store/chatSlice";
import {
  setSelectedConversationId,
  startNewConversation,
} from "../../store/appSlice";
import {
  addNewConversation,
  updateConversation, // eslint-disable-line @typescript-eslint/no-unused-vars
} from "../../store/chatHistorySlice";
import { clearCitation } from "../../store/citationSlice";
import {
  type ChartDataResponse,
  type Conversation,
  type ConversationRequest,
  type ParsedChunk,
  type ChatMessage,
  type Citation,
} from "../../types/AppTypes";
import { ChatAdd24Regular } from "@fluentui/react-icons";
import { generateUUIDv4 } from "../../configs/Utils";
import ChatMessageComponent from "../ChatMessage/ChatMessage";
import { getChatLandingText } from "../../config";
import {
  parseChartContent,
  isMalformedChartJSON,
} from "../../utils/jsonUtils";

type ChatProps = {
  onHandlePanelStates: (name: string) => void;
  panels: Record<string, string>;
  panelShowStates: Record<string, boolean>;
};

const [ASSISTANT, ERROR, USER] = ["assistant", "error", "user"];

const chatLandingText = getChatLandingText();

const Chat: React.FC<ChatProps> = ({
  onHandlePanelStates,
  panelShowStates,
  panels,
}) => {
  const dispatch = useAppDispatch();
  const { userMessage, generatingResponse, messages, isStreamingInProgress } = useAppSelector((state) => state.chat);
  const selectedConversationId = useAppSelector((state) => state.app.selectedConversationId);
  const generatedConversationId = useAppSelector((state) => state.app.generatedConversationId);
  const conversationHistory = useAppSelector((state) => state.chatHistory.list);
  const { isFetchingConvMessages, isHistoryUpdateAPIPending } = useAppSelector((state) => state.chatHistory);
  const questionInputRef = useRef<HTMLTextAreaElement>(null);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const abortFuncs = useRef([] as AbortController[]);
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);
  
  // Memoized computed values
  const currentConversationId = useMemo(() => 
    selectedConversationId || generatedConversationId,
    [selectedConversationId, generatedConversationId]
  );

  const hasMessages = useMemo(() => messages.length > 0, [messages.length]);
  
  const isInputDisabled = useMemo(() => 
    generatingResponse || isHistoryUpdateAPIPending,
    [generatingResponse, isHistoryUpdateAPIPending]
  );

  const isSendDisabled = useMemo(() => 
    generatingResponse || !userMessage.trim() || isHistoryUpdateAPIPending,
    [generatingResponse, userMessage, isHistoryUpdateAPIPending]
  );
  
  const saveToDB = useCallback(async (newMessages: ChatMessage[], convId: string, reqType: string = 'Text') => {
    if (!convId || !newMessages.length) {
      return;
    }

    try {
      const result = await dispatch(updateConversation({ conversationId: convId, messages: newMessages })).unwrap();
      const savedConversationId = result?.data?.conversation_id;
      const hasConversationInList = savedConversationId
        ? conversationHistory.some((conversation) => conversation.id === savedConversationId)
        : false;
      
      if (result?.success && savedConversationId && !hasConversationInList) {
        const newConversation: Conversation = {
          id: savedConversationId,
          title: result?.data?.title,
          messages: newMessages,
          date: result?.data?.date,
          updatedAt: result?.data?.date,
        };
        dispatch(addNewConversation(newConversation));
      }

      if (result?.success && savedConversationId && selectedConversationId !== savedConversationId) {
        dispatch(setSelectedConversationId(savedConversationId));
      }
    } catch {
      // Error saving data to database
    } finally {
      dispatch(setGeneratingResponse(false));
    }
  }, [selectedConversationId, conversationHistory, dispatch]);
  const parseCitationFromMessage = useCallback((message: string) => {
  try {
    const parsed = JSON.parse(message);
    if (Array.isArray(parsed)) {
      return parsed.filter(
        (c: Citation & { title?: string }) => c.url?.trim() || c.source?.trim() || (c as any).title?.trim()
      );
    }
  } catch {
    // Not parseable
  }
  return [];
}, []);

  const isChartQuery = useCallback((query: string) => {
    const chartKeywords = ["chart", "graph", "visualize", "plot"];
    
    // Convert to lowercase for case-insensitive matching
    const lowerCaseQuery = query.toLowerCase();
    
    // Use word boundary regex to match whole words only
    return chartKeywords.some(keyword => 
      new RegExp(`\\b${keyword}\\b`).test(lowerCaseQuery)
    );
  }, []);

  useEffect(() => {
    if (generatingResponse || isStreamingInProgress) {
      const chatAPISignal = abortFuncs.current.shift();
      if (chatAPISignal) {
        chatAPISignal.abort(
          "Chat Aborted due to switch to other conversation while generating"
        );
      }
    }
  }, [selectedConversationId]);

  useEffect(() => {
    if (
      !isFetchingConvMessages &&
      chatMessageStreamEnd.current
    ) {
      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "auto" });
      }, 100);
    }
  }, [isFetchingConvMessages]);

  const scrollChatToBottom = useCallback(() => {
    if (chatMessageStreamEnd.current) {
      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    }
  }, []);

  useEffect(() => {
    scrollChatToBottom();
  }, [generatingResponse, scrollChatToBottom]);

  // Helper function to create and dispatch a message
  const createAndDispatchMessage = useCallback((role: string, content: string | ChartDataResponse, shouldScroll: boolean = true): ChatMessage => {
    const message: ChatMessage = {
      id: generateUUIDv4(),
      role,
      content,
      date: new Date().toISOString(),
    };
    
    dispatch(addMessages([message]));
    
    if (shouldScroll) scrollChatToBottom();
    
    return message;
  }, [dispatch, scrollChatToBottom]);

  // Helper function to extract chart data from response
  const extractChartData = useCallback((chartResponse: ChartDataResponse | string): ChartDataResponse | string => {
    if (typeof chartResponse === 'object' && 'answer' in chartResponse) {
      return !chartResponse.answer || 
             (typeof chartResponse.answer === "object" && Object.keys(chartResponse.answer).length === 0)
        ? "Chart can't be generated, please try again."
        : chartResponse.answer;
    } 
    
    if (typeof chartResponse === 'string') {
      try {
        const parsed = JSON.parse(chartResponse);
        if (parsed && typeof parsed === 'object' && 'answer' in parsed) {
          return !parsed.answer ||
                 (typeof parsed.answer === "object" && Object.keys(parsed.answer).length === 0)
            ? "Chart can't be generated, please try again."
            : parsed.answer;
        }
      } catch {
        // Fall through to default
      }
      return "Chart can't be generated, please try again.";
    }
    
    return chartResponse;
  }, []);

  const makeApiRequestForChart = async (
    question: string,
    conversationId: string
  ) => {
    if (generatingResponse || !question.trim()) return;

    const newMessage: ChatMessage = {
      id: generateUUIDv4(),
      role: USER,
      content: question,
      date: new Date().toISOString()
    };
    
    dispatch(setGeneratingResponse(true));
    
    dispatch(addMessages([newMessage]));
    
    dispatch(setUserMessageAction(questionInputRef?.current?.value || ""));
    
    scrollChatToBottom();
    
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      query: question
    };

    let updatedMessages: ChatMessage[] = [];
    
    try {
      const result = await dispatch(sendMessage({ request, abortSignal: abortController.signal }));
      if (!sendMessage.fulfilled.match(result)) {
        throw new Error('Failed to send message');
      }
      const response = result.payload;

      if (response?.body) {
        const reader = response.body.getReader();
        let runningText = "";
        let hasError = false;
        
        // Read stream
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = new TextDecoder("utf-8").decode(value);
          try {
            const textObj = JSON.parse(text);
            if (textObj?.object?.data) {
              runningText = text;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = text;
            }
          } catch (e) {
            // Non-JSON chunk, continue
          }
        }
        
        // Process response
        if (hasError) {
          const errorMsg = JSON.parse(runningText).error;
          const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
          updatedMessages = [newMessage, errorMessage];
        } else if (isChartQuery(question)) {
          try {
            const parsedResponse = JSON.parse(runningText);
            
            if ((parsedResponse?.object?.type || parsedResponse?.object?.chartType) && parsedResponse?.object?.data) {
              const chartMessage = createAndDispatchMessage(
                ASSISTANT, 
                parsedResponse.object as unknown as ChartDataResponse
              );
              updatedMessages = [newMessage, chartMessage];
            } else if (parsedResponse.error || parsedResponse?.object?.message) {
              const errorMsg = parsedResponse.error || parsedResponse.object.message;
              const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
              updatedMessages = [newMessage, errorMessage];
            }
          } catch {
            // Error parsing chart response
          }
        }
      }
      
      if (updatedMessages.length > 0) {
        saveToDB(updatedMessages, conversationId, 'graph');
      }
    } catch (e) {
      // Error in chart API request

      if (abortController.signal.aborted) {
        updatedMessages = [newMessage];
        saveToDB(updatedMessages, conversationId, 'graph');
      } else if (e instanceof Error) {
        alert(e.message);
      } else {
        alert("An error occurred. Please try again. If the problem persists, please contact the site administrator.");
      }
    } finally {
      dispatch(setGeneratingResponse(false));
      dispatch(setStreamingFlag(false));
      setIsChartLoading(false);
      abortController.abort();
    }
  };

  const makeApiRequestWithCosmosDB = async (
    question: string,
    conversationId: string
  ) => {
    if (generatingResponse || !question.trim()) return;
    
    const isChatReq = isChartQuery(userMessage) ? "graph" : "Text";
    const newMessage: ChatMessage = {
      id: generateUUIDv4(),
      role: USER,
      content: question,
      date: new Date().toISOString(),
    };
    
    dispatch(setGeneratingResponse(true));
    
    dispatch(addMessages([newMessage]));
    
    dispatch(setUserMessageAction(""));
    
    scrollChatToBottom();
    
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      query: userMessage
    };

    const streamMessage: ChatMessage = {
      id: generateUUIDv4(),
      date: new Date().toISOString(),
      role: ASSISTANT,
      content: "",
      citations: "",
    };
    
    let updatedMessages: ChatMessage[] = [];
    
    try {
      const result = await dispatch(sendMessage({ request, abortSignal: abortController.signal }));
      if (!sendMessage.fulfilled.match(result)) {
        throw new Error('Failed to send message');
      }
      const response = result.payload;

      if (response?.body) {
        let isChartResponseReceived = false;
        const reader = response.body.getReader();
        let runningText = "";
        let hasError = false;
        let lineBuffer = ""; // Carry-over buffer for partial JSON lines
        
        // Read and process stream
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = new TextDecoder("utf-8").decode(value);
          
          try {
            const textObj = JSON.parse(text);
            if (textObj?.object?.data || textObj?.object?.message) {
              runningText = text;
              isChartResponseReceived = true;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = text;
            }
          } catch (e) {
            // Not JSON, continue processing as stream
          }
          
          if (!isChartResponseReceived) {
            // Prepend any leftover partial line from previous chunk
            const combined = lineBuffer + text;
            const lines = combined.split("\n");
            // Last element may be incomplete — carry it over
            lineBuffer = lines.pop() || "";

            lines.forEach((textValue) => {
              if (!textValue || textValue === "{}") return;
              
              try {
                const parsed: ParsedChunk = JSON.parse(textValue);
                
                if (parsed?.error && !hasError) {
                  hasError = true;
                  runningText = parsed?.error;
                } else if (typeof parsed === "object" && !hasError) {
                  const delta = parsed?.choices?.[0]?.delta;
                  const legacyMsg = parsed?.choices?.[0]?.messages?.[0];
                  // Delta format (Python) yields incremental fragments;
                  // messages format (dotnet) yields the full accumulated text each time.
                  if (delta) {
                    const role = delta.role;
                    const content = delta.content;
                    if (role === "tool" && content) {
                      streamMessage.citations = content;
                    } else if (role === "assistant" && content) {
                      if (isChartQuery(userMessage)) {
                        runningText += content;
                      } else {
                        streamMessage.content = (streamMessage.content || "") + content;
                        streamMessage.role = ASSISTANT;
                      }
                    }
                    if (!isChartQuery(userMessage)) {
                      dispatch(updateMessageById({ ...streamMessage }));
                      scrollChatToBottom();
                    }
                  } else if (legacyMsg) {
                    const role = legacyMsg.role;
                    const content = legacyMsg.content;
                    if (role === "assistant" && content) {
                      if (isChartQuery(userMessage)) {
                        runningText = content;
                      } else {
                        // Dotnet sends full accumulated text — replace, not append
                        streamMessage.content = content;
                        streamMessage.role = ASSISTANT;
                      }
                    }
                    if (!isChartQuery(userMessage)) {
                      dispatch(updateMessageById({ ...streamMessage }));
                      scrollChatToBottom();
                    }
                  } else if (isChartQuery(userMessage)) {
                    // Legacy chart format fallback
                    runningText += textValue;
                  }
                }
              } catch (e) {
                // Skip malformed chunks
              }
            });
            
            if (hasError) break;
          }
        }
        
        // END OF STREAMING - Process final response
        if (hasError) {
          const parsedError = JSON.parse(runningText);
          const errorMsg = parsedError.error === "Attempted to access streaming response content, without having called `read()`." 
            ? "An error occurred. Please try again later." 
            : parsedError.error;
          
          const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
          updatedMessages = [newMessage, errorMessage];
        } else if (isChartQuery(userMessage)) {
          try {
            // Delta format: runningText is the accumulated chart JSON content directly
            // Legacy format: runningText is concatenated delta JSON lines — split and take last segment
            let chartTextToParse: string;
            
            // Try parsing directly first (delta format accumulates content only)
            try {
              JSON.parse(runningText);
              chartTextToParse = runningText;
            } catch {
              // Legacy fallback: split concatenated JSON objects
              const splitRunningText = runningText.split("}{");
              const lastSegment = splitRunningText.length > 1
                ? "{" + splitRunningText[splitRunningText.length - 1]
                : splitRunningText[0];
              
              // Check if legacy format with choices[0].messages[0].content
              try {
                const legacyParsed = JSON.parse(lastSegment);
                const legacyContent = legacyParsed?.choices?.[0]?.messages?.[0]?.content;
                chartTextToParse = typeof legacyContent === "string" ? legacyContent : lastSegment;
              } catch {
                chartTextToParse = lastSegment;
              }
            }
            
            const parsedChartContent = JSON.parse(chartTextToParse);
            
            // Use helper function for parsing — parsedChartContent is the chart object directly
            let chartResponse = typeof parsedChartContent === "string" 
              ? parseChartContent(parsedChartContent) 
              : parsedChartContent || "Chart can't be generated, please try again.";

            chartResponse = extractChartData(chartResponse);

            // Validate and create chart message
            if ((chartResponse?.type || chartResponse?.chartType) && chartResponse?.data) {
              // Valid chart data
              const chartMessage = createAndDispatchMessage(
                ASSISTANT, 
                chartResponse as unknown as ChartDataResponse
              );
              updatedMessages = [newMessage, chartMessage];
            } else {
              let displayContent = typeof parsedChartContent === "string" 
                ? parsedChartContent 
                : JSON.stringify(parsedChartContent);
              
              try {
                const parsed = typeof parsedChartContent === "object" ? parsedChartContent : JSON.parse(displayContent);
                if (parsed && typeof parsed === "object" && "answer" in parsed) {
                  displayContent = parsed.answer;
                }
              } catch {
                // keep displayContent as-is
              }
              
              let errorMsg = displayContent;
              
              // Use helper function for validation
              if (isMalformedChartJSON(errorMsg, false)) {
                errorMsg = "Chart can not be generated, please try again later";
              }
              
              const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
              updatedMessages = [newMessage, errorMessage];
            }
          } catch {
            // Error parsing chart response
          }
        }
        
        // If no messages have been added yet but we have streamed content, save it
        if (updatedMessages.length === 0 && streamMessage.content) {
          // Dotnet backend may wrap final content as {"answer":"...", "citations":[]}
          if (typeof streamMessage.content === "string") {
            try {
              const finalParsed = JSON.parse(streamMessage.content);
              if (finalParsed && typeof finalParsed === "object" && "answer" in finalParsed) {
                streamMessage.content = finalParsed.answer;
                if (finalParsed.citations && JSON.stringify(finalParsed.citations) !== "[]") {
                  streamMessage.citations = JSON.stringify(finalParsed.citations);
                }
              }
            } catch {
              // Not JSON — use content as-is
            }
          }
          updatedMessages = [newMessage, streamMessage];
        }
      }
      
      if (updatedMessages.length > 0) {
        saveToDB(updatedMessages, conversationId, isChatReq);
      }
    } catch (e) {
      // Error in API request

      if (abortController.signal.aborted) {
        updatedMessages = streamMessage.content
          ? [newMessage, streamMessage]
          : [newMessage];
        
        saveToDB(updatedMessages, conversationId, 'error');
      } else if (e instanceof Error) {
        alert(e.message);
      } else {
        alert("An error occurred. Please try again. If the problem persists, please contact the site administrator.");
      }
    } finally {
      dispatch(setGeneratingResponse(false));
      dispatch(setStreamingFlag(false));
      abortController.abort();
    }
  };

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isInputDisabled) {
        return;
      }
      if (userMessage) {
        makeApiRequestWithCosmosDB(userMessage, currentConversationId);
      }
      if (questionInputRef?.current) {
        questionInputRef?.current.focus();
      }
    }
  }, [isInputDisabled, userMessage, currentConversationId]);

  const onClickSend = useCallback(() => {
    if (isInputDisabled) {
      return;
    }
    if (userMessage) {
      makeApiRequestWithCosmosDB(userMessage, currentConversationId);
    }
    if (questionInputRef?.current) {
      questionInputRef?.current.focus();
    }
  }, [isInputDisabled, userMessage, currentConversationId]);

  const setUserMessage = useCallback((value: string) => {
    dispatch(setUserMessageAction(value));
  }, [dispatch]);

  const onNewConversation = useCallback(() => {
    dispatch(startNewConversation());
    dispatch(clearChat());
    dispatch(clearCitation());
  }, [dispatch]);
  return (
    <div className="chat-container">
      <div className="chat-header">
        <Subtitle2>Chat</Subtitle2>
        <span>
          <Button
            appearance="outline"
            onClick={() => onHandlePanelStates(panels.CHATHISTORY)}
            className="hide-chat-history"
          >
            {`${panelShowStates?.[panels.CHATHISTORY] ? "Hide" : "Show"
              } Chat History`}
          </Button>
        </span>
      </div>
      <div className="chat-messages">
        {Boolean(isFetchingConvMessages) && (
          <div style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            height: '100%',
            minHeight: '300px'
          }}>
            <Spinner
              size={SpinnerSize.medium}
              aria-label="Fetching Chat messages"
            />
          </div>
        )}
        {!isFetchingConvMessages && !hasMessages && (
          <div className="initial-msg">
            <h2>✨</h2>
            <Subtitle2>Start Chatting</Subtitle2>
            <Body1 style={{ textAlign: "center" }}>
              {chatLandingText}
            </Body1>
          </div>
        )}
        {!isFetchingConvMessages &&
          messages.map((msg, index) => {
            const isLastAssistantMessage = msg.role === "assistant" && index === messages.length - 1;
            
            return (
              <div key={msg.id || index} className={`chat-message ${msg.role}`}>
                <ChatMessageComponent
                  message={msg}
                  index={index}
                  isLastAssistantMessage={isLastAssistantMessage}
                  generatingResponse={generatingResponse}
                  parseCitationFromMessage={parseCitationFromMessage}
                />
              </div>
            );
          })}
        {((generatingResponse && !isStreamingInProgress) || isChartLoading)  && (
          <div className="assistant-message loading-indicator">
            <div className="typing-indicator">
              <span className="generating-text">{isChartLoading ? "Generating chart if possible with the provided data" : "Generating answer"} </span>
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}
        <div data-testid="streamendref-id" ref={chatMessageStreamEnd} />
      </div>
      <div className="chat-footer">
        <Button
          className="btn-create-conv"
          shape="circular"
          appearance="primary"
          icon={<ChatAdd24Regular />}
          onClick={onNewConversation}
          title="Create new Conversation"
          disabled={isInputDisabled}
        />
        <div className="text-area-container">
          <Textarea
            className="textarea-field"
            value={userMessage}
            onChange={(e, data) => setUserMessage(data.value || "")}
            placeholder="Ask a question..."
            onKeyDown={handleKeyDown}
            ref={questionInputRef}
            rows={2}
            style={{ resize: "none" }}
            appearance="outline"
          />
          <DefaultButton
            iconProps={{ iconName: "Send" }}
            role="button"
            onClick={onClickSend}
            disabled={isSendDisabled}
            className="send-button"
            aria-disabled={isSendDisabled}
            title="Send Question"
          />
        </div>
      </div>
    </div>
  );
};

export default Chat;
