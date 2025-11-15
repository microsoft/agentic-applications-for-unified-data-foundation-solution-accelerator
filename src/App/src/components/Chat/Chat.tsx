import React, { useEffect, useRef, useState } from "react";
import {
  Button,
  Textarea,
  Subtitle2,
  Body1,
} from "@fluentui/react-components";
import "./Chat.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from "remark-supersub";
import { DefaultButton, Spinner, SpinnerSize } from "@fluentui/react";
import { useAppContext } from "../../state/useAppContext";
import { actionConstants } from "../../state/ActionConstants";
import {
  type ChartDataResponse,
  type Conversation,
  type ConversationRequest,
  type ParsedChunk,
  type ChatMessage,
  ToolMessageContent,
} from "../../types/AppTypes";
import { callConversationApi, historyUpdate } from "../../api/api";
import { ChatAdd24Regular } from "@fluentui/react-icons";
import { generateUUIDv4 } from "../../configs/Utils";
import ChatChart from "../ChatChart/ChatChart";
import Citations from "../Citations/Citations";
import { getChatLandingText } from "../../config";

type ChatProps = {
  onHandlePanelStates: (name: string) => void;
  panels: Record<string, string>;
  panelShowStates: Record<string, boolean>;
};

const [ASSISTANT, TOOL, ERROR, USER] = ["assistant", "tool", "error", "user"];

const chatLandingText = getChatLandingText();

const Chat: React.FC<ChatProps> = ({
  onHandlePanelStates,
  panelShowStates,
  panels,
}) => {
  const { state, dispatch } = useAppContext();
  const { userMessage, generatingResponse } = state?.chat;
  const questionInputRef = useRef<HTMLTextAreaElement>(null);
  const [isChartLoading, setIsChartLoading] = useState(false)
  const abortFuncs = useRef([] as AbortController[]);
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);
  const [isCharthDisplayDefault , setIsCharthDisplayDefault] = useState(false);
  
  const saveToDB = async (messages: ChatMessage[], convId: string, reqType: string = 'Text') => {
    if (!convId || !messages.length) {
      return;
    }
    const isNewConversation = reqType !== 'graph' ? !state.selectedConversationId : false;
    dispatch({
      type: actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG,
      payload: true,
    });

    if (((reqType !== 'graph' && reqType !== 'error') &&  messages[messages.length - 1].role !== ERROR) && isCharthDisplayDefault ){
      setIsChartLoading(true);
      setTimeout(()=>{
        makeApiRequestForChart('show in a graph by default', convId, messages[messages.length - 1].content as string)
      },5000)
      
    }
    await historyUpdate(messages, convId)
      .then(async (res) => {
        if (!res.ok) {
          if (!messages) {
            let err: Error = {
              ...new Error(),
              message: "Failure fetching current chat state.",
            };
            throw err;
          }
        }     
        let responseJson = await res.json();
        if (isNewConversation && responseJson?.success) {
          const newConversation: Conversation = {
            id: responseJson?.data?.conversation_id,
            title: responseJson?.data?.title,
            messages: messages,
            date: responseJson?.data?.date,
            updatedAt: responseJson?.data?.date,
          };
          dispatch({
            type: actionConstants.ADD_NEW_CONVERSATION_TO_CHAT_HISTORY,
            payload: newConversation,
          });
          dispatch({
            type: actionConstants.UPDATE_SELECTED_CONV_ID,
            payload: responseJson?.data?.conversation_id,
          });
        }
        dispatch({
          type: actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG,
          payload: false,
        });
        return res as Response;
      })
      .catch((err) => {
        console.error("Error: while saving data", err);
      })
      .finally(() => {
        dispatch({
          type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
          payload: false,
        });
        dispatch({
          type: actionConstants.UPDATE_HISTORY_UPDATE_API_FLAG,
          payload: false,
        });  
      });
  };


  const parseCitationFromMessage = (message: any) => {
  try {
    message = '{' + message;
    const toolMessage = JSON.parse(message as string) as ToolMessageContent;

    if (toolMessage?.citations?.length) {
      return toolMessage.citations.filter(
        (c) => c.url?.trim() || c.title?.trim()
      );
    }
  } catch {
        // console.log("ERROR WHIEL PARSING TOOL CONTENT");
  }
  return [];
};
  const isChartQuery = (query: string) => {
    const chartKeywords = ["chart", "graph", "visualize", "plot"];
    
    // Convert to lowercase for case-insensitive matching
    const lowerCaseQuery = query.toLowerCase();
    
    // Use word boundary regex to match whole words only
    return chartKeywords.some(keyword => 
      new RegExp(`\\b${keyword}\\b`).test(lowerCaseQuery)
    );
  };

  useEffect(() => {
    if (state.chat.generatingResponse || state.chat.isStreamingInProgress) {
      const chatAPISignal = abortFuncs.current.shift();
      if (chatAPISignal) {
        chatAPISignal.abort(
          "Chat Aborted due to switch to other conversation while generating"
        );
      }
    }
  }, [state.selectedConversationId]);

  useEffect(() => {
    if (
      !state.chatHistory.isFetchingConvMessages &&
      chatMessageStreamEnd.current
    ) {
      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "auto" });
      }, 100);
    }
  }, [state.chatHistory.isFetchingConvMessages]);

  const scrollChatToBottom = () => {
    if (chatMessageStreamEnd.current) {
      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    }
  };

  useEffect(() => {
    scrollChatToBottom();
  }, [state.chat.generatingResponse]);

  // Helper function to create and dispatch a message
  const createAndDispatchMessage = (role: string, content: string | ChartDataResponse, shouldScroll: boolean = true): ChatMessage => {
    const message: ChatMessage = {
      id: generateUUIDv4(),
      role,
      content,
      date: new Date().toISOString(),
    };
    
    dispatch({
      type: actionConstants.UPDATE_MESSAGES,
      payload: [message],
    });
    
    if (shouldScroll) scrollChatToBottom();
    
    return message;
  };

  const makeApiRequestForChart = async (
    question: string,
    conversationId: string,
    lrg: string
  ) => {
    if (generatingResponse || !question.trim()) return;

    const newMessage: ChatMessage = {
      id: generateUUIDv4(),
      role: USER,
      content: question,
      date: new Date().toISOString()
    };
    
    dispatch({
      type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
      payload: true,
    });
    
    dispatch({
      type: actionConstants.UPDATE_MESSAGES,
      payload: [newMessage],
    });
    
    dispatch({
      type: actionConstants.UPDATE_USER_MESSAGE,
      payload: questionInputRef?.current?.value || "",
    });
    
    scrollChatToBottom();
    
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      messages: [...state.chat.messages, newMessage].filter(msg => msg.role !== ERROR),
      last_rag_response: lrg
    };

    let updatedMessages: ChatMessage[] = [];
    
    try {
      const response = await callConversationApi(request, abortController.signal);

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
          updatedMessages = [...state.chat.messages, newMessage, errorMessage];
        } else if (isChartQuery(question)) {
          try {
            const parsedResponse = JSON.parse(runningText);
            
            if (parsedResponse?.object?.type && parsedResponse?.object?.data) {
              const chartMessage = createAndDispatchMessage(
                ASSISTANT, 
                parsedResponse.object as unknown as ChartDataResponse
              );
              updatedMessages = [...state.chat.messages, newMessage, chartMessage];
            } else if (parsedResponse.error || parsedResponse?.object?.message) {
              const errorMsg = parsedResponse.error || parsedResponse.object.message;
              const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
              updatedMessages = [...state.chat.messages, newMessage, errorMessage];
            }
          } catch (e) {
            console.error("Error parsing chart response:", e);
          }
        }
      }
      
      if (updatedMessages.length > 0) {
        saveToDB(updatedMessages, conversationId, 'graph');
      }
    } catch (e) {
      console.error("Error in makeApiRequestForChart:", e);
      
      if (abortController.signal.aborted) {
        updatedMessages = [...state.chat.messages, newMessage];
        saveToDB(updatedMessages, conversationId, 'graph');
      } else if (e instanceof Error) {
        alert(e.message);
      } else {
        alert("An error occurred. Please try again. If the problem persists, please contact the site administrator.");
      }
    } finally {
      dispatch({
        type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
        payload: false,
      });
      dispatch({
        type: actionConstants.UPDATE_STREAMING_FLAG,
        payload: false,
      });
      setIsChartLoading(false);
      abortController.abort();
    }
  };

  // Helper function to extract answer and citations from response content
  const extractAnswerAndCitations = (responseContent: string): { answerText: string; citationString: string } => {
    let answerText = '';
    let citationString = '';
    
    const answerKey = `"answer":`;
    const answerStartIndex = responseContent.indexOf(answerKey);
    
    // If no "answer" key found, treat the entire response as plain text
    if (answerStartIndex === -1) {
      return { answerText: responseContent, citationString: '' };
    }
    
    const answerTextStart = answerStartIndex + 9;
    const citationsKey = `"citations":`;
    const citationsStartIndex = responseContent.indexOf(citationsKey);
    
    if (citationsStartIndex > answerTextStart) {
      answerText = responseContent.substring(answerTextStart, citationsStartIndex).trim();
      citationString = responseContent.substring(citationsStartIndex).trim();
    } else {
      answerText = responseContent.substring(answerTextStart).trim();
    }
    
    answerText = answerText
      .replace(/^"+|"+$|,$/g, '')
      .replace(/[",]+$/, '')
      .replace(/\\n/g, "  \n");
    
    return { answerText, citationString };
  };

const sanitizeJSONString = (jsonString: string): string => {
  if (!jsonString || typeof jsonString !== 'string') {
    return jsonString;
  }

  let sanitized = jsonString;

  try {
    // **NEW: Try parsing first - if it works, no sanitization needed!**
    try {
      JSON.parse(sanitized);
      console.log("✅ JSON is already valid, skipping sanitization");
      return sanitized;
    } catch {
      console.log("🔧 JSON invalid, proceeding with sanitization...");
    }

    // **STEP 0: Handle escaped JSON strings (e.g., "{\"type\":\"bar\"...}")**
    // Check if the entire string is a JSON-escaped string wrapped in quotes
    if (sanitized.startsWith('"{') && sanitized.endsWith('}"')) {
      console.log('🔧 Detected escaped JSON string with outer quotes, removing...');
      // Remove outer quotes
      sanitized = sanitized.slice(1, -1);
    }
    
    // **ALWAYS unescape backslashes** (regardless of outer quotes)
    console.log('🧹 Unescaping backslashes...');
    sanitized = sanitized.replace(/\\"/g, '"');      // \" → "
    sanitized = sanitized.replace(/\\\\/g, '\\');    // \\ → \
    sanitized = sanitized.replace(/\\n/g, '\n');     // \n → newline
    sanitized = sanitized.replace(/\\r/g, '\r');     // \r → carriage return
    sanitized = sanitized.replace(/\\t/g, '\t');     // \t → tab

    // **NEW: Validate after basic unescaping**
    try {
      JSON.parse(sanitized);
      console.log("✅ JSON valid after basic unescaping, skipping complex sanitization");
      return sanitized;
    } catch {
      console.log("🔧 Still invalid, continuing with complex sanitization...");
    }

    // Helper function to find the matching closing bracket
    const findMatchingBracket = (str: string, startIndex: number): number => {
      let depth = 0;
      const openBracket = str[startIndex];
      const closeBracket = openBracket === '{' ? '}' : ')';
      
      for (let i = startIndex; i < str.length; i++) {
        if (str[i] === openBracket || (openBracket === '(' && str[i] === '{')) {
          depth++;
        } else if (str[i] === closeBracket || (closeBracket === ')' && str[i] === '}')) {
          depth--;
          if (depth === 0) {
            return i;
          }
        }
      }
      return -1; // No matching bracket found
    };

    // 1. Remove function declarations with balanced brackets: function name(...) { ... }
    let pos = 0;
    while (pos < sanitized.length) {
      // Look for "function" keyword
      const functionMatch = sanitized.substring(pos).match(/:\s*function\s*\w*\s*\(/);
      if (!functionMatch) break;
      
      const functionStart = pos + functionMatch.index!;
      const parenStart = sanitized.indexOf('(', functionStart);
      
      if (parenStart === -1) break;
      
      // Find matching closing parenthesis
      const parenEnd = findMatchingBracket(sanitized, parenStart);
      if (parenEnd === -1) break;
      
      // Find opening brace after parameters
      const braceStart = sanitized.indexOf('{', parenEnd);
      if (braceStart === -1 || braceStart > parenEnd + 10) {
        pos = parenEnd + 1;
        continue;
      }
      
      // Find matching closing brace
      const braceEnd = findMatchingBracket(sanitized, braceStart);
      if (braceEnd === -1) break;
      
      // Replace the entire function with "[Function]"
      sanitized = 
        sanitized.substring(0, functionStart) + 
        ': "[Function]"' + 
        sanitized.substring(braceEnd + 1);
      
      pos = functionStart + 13; // Length of ': "[Function]"'
    }

    // 2. Remove arrow functions with balanced brackets: (...) => { ... }
    pos = 0;
    while (pos < sanitized.length) {
      // Look for arrow function pattern
      const arrowMatch = sanitized.substring(pos).match(/:\s*\([^)]*\)\s*=>\s*\{/);
      if (!arrowMatch) break;
      
      const arrowStart = pos + arrowMatch.index!;
      const braceStart = sanitized.indexOf('{', arrowStart);
      
      if (braceStart === -1) break;
      
      // Find matching closing brace with balanced brackets
      const braceEnd = findMatchingBracket(sanitized, braceStart);
      if (braceEnd === -1) break;
      
      // Replace the entire arrow function
      sanitized = 
        sanitized.substring(0, arrowStart) + 
        ': "[Function]"' + 
        sanitized.substring(braceEnd + 1);
      
      pos = arrowStart + 13;
    }

    // 3. Remove standalone function patterns (not preceded by colon)
    pos = 0;
    while (pos < sanitized.length) {
      const funcMatch = sanitized.substring(pos).match(/\bfunction\s*\w*\s*\(/);
      if (!funcMatch) break;
      
      const funcStart = pos + funcMatch.index!;
      
      // Check if it's NOT preceded by a colon (already handled above)
      if (funcStart > 0 && sanitized.substring(Math.max(0, funcStart - 10), funcStart).includes(':')) {
        pos = funcStart + 1;
        continue;
      }
      
      const parenStart = sanitized.indexOf('(', funcStart);
      if (parenStart === -1) break;
      
      const parenEnd = findMatchingBracket(sanitized, parenStart);
      if (parenEnd === -1) break;
      
      const braceStart = sanitized.indexOf('{', parenEnd);
      if (braceStart === -1 || braceStart > parenEnd + 10) {
        pos = parenEnd + 1;
        continue;
      }
      
      const braceEnd = findMatchingBracket(sanitized, braceStart);
      if (braceEnd === -1) break;
      
      sanitized = 
        sanitized.substring(0, funcStart) + 
        '"[Function]"' + 
        sanitized.substring(braceEnd + 1);
      
      pos = funcStart + 12;
    }

    // 4. Remove arrow functions with simple expressions (no braces)
    sanitized = sanitized.replace(
      /:\s*\([^)]*\)\s*=>\s*`[^`]*`/g,
      ': "[Function]"'
    );

    sanitized = sanitized.replace(
      /:\s*\([^)]*\)\s*=>\s*[^,}\]]+/g,
      ': "[Function]"'
    );

    // 5. Remove any remaining arrow function patterns without balanced bracket handling
    sanitized = sanitized.replace(
      /\([^)]*\)\s*=>/g,
      '"[Function]"'
    );

    // 6. Remove template literal expressions: ${...}
    sanitized = sanitized.replace(
      /\$\{[^}]*\}/g,
      '[Expression]'
    );

    // 7. Remove template literals: `...`
    sanitized = sanitized.replace(
      /`[^`]*`/g,
      '"[Template]"'
    );

    // 8. Convert single quotes to double quotes for property values
    sanitized = sanitized.replace(
      /:\s*'([^']*)'/g,
      ': "$1"'
    );

    // 9. Remove trailing commas before closing braces/brackets
    sanitized = sanitized.replace(
      /,(\s*[}\]])/g,
      '$1'
    );

    // 10. Clean up any remaining malformed patterns
    // **COMMENTED OUT** - This regex is too broad and removes valid JSON objects
    // Steps 1-5 already handle all function patterns with balanced bracket matching
    // sanitized = sanitized.replace(
    //   /=>\s*\{[^}]*\}/g,
    //   '"[Function]"'
    // );

    // **11. Ensure all JSON keys are enclosed in double quotes**
    // Match unquoted keys: {key: value} or ,key: value
    // Regex: ([\{\,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:
    sanitized = sanitized.replace(
      /([\{\,]\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:/g,
      '$1"$2":'
    );
    

  } catch (error) {
    console.error('Error during JSON sanitization:', error);
    return jsonString;
  }

  return sanitized;
};

  // Helper function to extract chart data from response
  const extractChartData = (chartResponse: any): any => {
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
    
    dispatch({
      type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
      payload: true,
    });
    
    dispatch({
      type: actionConstants.UPDATE_MESSAGES,
      payload: [newMessage],
    });
    
    dispatch({
      type: actionConstants.UPDATE_USER_MESSAGE,
      payload: "",
    });
    
    scrollChatToBottom();
    
    const abortController = new AbortController();
    abortFuncs.current.unshift(abortController);

    const request: ConversationRequest = {
      id: conversationId,
      messages: [...state.chat.messages, newMessage].filter(msg => msg.role !== ERROR),
      last_rag_response:
        isChartQuery(userMessage) && state.chat.lastRagResponse
          ? JSON.stringify(state.chat.lastRagResponse)
          : null,
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
      const response = await callConversationApi(request, abortController.signal);

      if (response?.body) {
        let isChartResponseReceived = false;
        const reader = response.body.getReader();
        let runningText = "";
        let hasError = false;
        
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
            // Text-based streaming response
            const objects = text.split("\n").filter((val) => val !== "");
            
            objects.forEach((textValue) => {
              if (!textValue || textValue === "{}") return;
              
              try {
                const parsed: ParsedChunk = JSON.parse(textValue);
                
                if (parsed?.error && !hasError) {
                  hasError = true;
                  runningText = parsed?.error;
                } else if (isChartQuery(userMessage) && !hasError) {
                  runningText += textValue;
                } else if (typeof parsed === "object" && !hasError) {
                  const responseContent = parsed?.choices?.[0]?.messages?.[0]?.content;
                  
                  if (responseContent) {
                    const { answerText, citationString } = extractAnswerAndCitations(responseContent);
                    streamMessage.content = answerText || "";
                    streamMessage.role = parsed?.choices?.[0]?.messages?.[0]?.role || ASSISTANT;
                    streamMessage.citations = citationString;
                    
                    dispatch({
                      type: actionConstants.UPDATE_MESSAGE_BY_ID,
                      payload: streamMessage,
                    });
                    scrollChatToBottom();
                  }
                }
              } catch (e) {
                // Skip malformed chunks
              }
            });
            
            if (hasError) {
              console.log("STOPPED DUE TO ERROR FROM API RESPONSE");
              break;
            }
          }
        }
        
        // END OF STREAMING - Process final response
        if (hasError) {
          const parsedError = JSON.parse(runningText);
          const errorMsg = parsedError.error === "Attempted to access streaming response content, without having called `read()`." 
            ? "An error occurred. Please try again later." 
            : parsedError.error;
          
          const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
          updatedMessages = [...state.chat.messages, newMessage, errorMessage];
        } else if (isChartQuery(userMessage)) {
          try {
            const splitRunningText = runningText.split("}{");
            const parsedChartResponse = JSON.parse("{" + splitRunningText[splitRunningText.length - 1]);
            
            const rawChartContent = parsedChartResponse?.choices[0]?.messages[0]?.content;
            let chartResponse: any = {};
            
            // Handle chart content parsing with sanitization
            if (typeof rawChartContent === "string") {
              console.log("📥 Raw chart content before JSON parse:", rawChartContent);
              
              try {
                // First, try to parse the raw content directly
                chartResponse = JSON.parse(rawChartContent);
                console.log("✅ Successfully parsed raw content directly");
                
                // **Handle nested escaped JSON in "answer" field**
                if (chartResponse && typeof chartResponse === "object" && "answer" in chartResponse) {
                  const answerValue = chartResponse.answer;
                  
                  // If answer is a STRING, it might be escaped JSON - parse it
                  if (typeof answerValue === "string") {
                    console.log("🔍 Answer is a string, length:", answerValue.length);
                    console.log("🔍 First 200 chars:", answerValue.substring(0, 200));
                    console.log("🔍 Last 200 chars:", answerValue.substring(Math.max(0, answerValue.length - 200)));
                    
                    try {
                      // **ENHANCED FIX**: Try direct parse first (for properly escaped JSON)
                      let parsedAnswer;
                      
                      try {
                        // Attempt 1: Direct parse (handles \" properly)
                        parsedAnswer = JSON.parse(answerValue);
                        console.log("✅ Direct parse succeeded");
                      } catch (directParseError) {
                        console.log("⚠️ Direct parse failed, trying sanitization...");
                        
                        // Attempt 2: Sanitize then parse
                        const sanitizedAnswer = sanitizeJSONString(answerValue);
                        console.log("🧹 Sanitized length:", sanitizedAnswer.length);
                        console.log("🧹 Sanitized first 200:", sanitizedAnswer.substring(0, 200));
                        
                        // Validate the sanitized string before parsing
                        const openBraces = (sanitizedAnswer.match(/\{/g) || []).length;
                        const closeBraces = (sanitizedAnswer.match(/\}/g) || []).length;
                        console.log(`📊 Brace count - Open: ${openBraces}, Close: ${closeBraces}`);
                        
                        if (openBraces !== closeBraces) {
                          console.error("❌ Unbalanced braces after sanitization!");
                          throw new Error("Sanitization produced unbalanced braces");
                        }
                        
                        parsedAnswer = JSON.parse(sanitizedAnswer);
                        console.log("✅ Parse succeeded after sanitization");
                      }
                      
                      // Replace the string answer with the parsed object
                      chartResponse.answer = parsedAnswer;
                      console.log("✅ Successfully processed nested JSON from answer field");
                      
                    } catch (nestedError) {
                      console.error("❌ Failed to parse nested JSON:", nestedError);
                      console.error("❌ Error details:", nestedError instanceof Error ? nestedError.message : String(nestedError));
                      
                      // Keep the original string and let the error handling below catch it
                      console.warn("⚠️ Keeping answer as string, will be caught by error handling");
                    }
                  }
                }
                
              } catch (parseError) {
                console.error("❌ Failed to parse raw content, trying sanitization...");
                
                // If direct parsing fails, try sanitizing first
                const sanitizedContent = sanitizeJSONString(rawChartContent);
                console.log("🧹 Sanitized content (first 200 chars):", sanitizedContent.substring(0, 200));
                
                try {
                  chartResponse = JSON.parse(sanitizedContent);
                  console.log("✅ Successfully parsed after sanitization");
                } catch (sanitizeError) {
                  console.error("❌ JSON parse failed even after sanitization:", sanitizeError instanceof Error ? sanitizeError.message : sanitizeError);
                  chartResponse = "Chart can't be generated, please try again.";
                }
              }
              
            } else {
              chartResponse = rawChartContent || "Chart can't be generated, please try again.";
            }
          
            chartResponse = extractChartData(chartResponse);

            if (chartResponse?.type && chartResponse?.data) {
              // Valid chart data
              const chartMessage = createAndDispatchMessage(
                ASSISTANT, 
                chartResponse as unknown as ChartDataResponse
              );
              updatedMessages = [...state.chat.messages, newMessage, chartMessage];
            } else if (parsedChartResponse?.error || parsedChartResponse?.choices[0]?.messages[0]?.content) {
              let content = parsedChartResponse?.choices[0]?.messages[0]?.content;
              let displayContent = content;
              
              try {
                const parsed = typeof content === "string" ? JSON.parse(content) : content;
                if (parsed && typeof parsed === "object" && "answer" in parsed) {
                  displayContent = parsed.answer;
                }
              } catch {
                displayContent = content;
              }
              
              const errorMsg = parsedChartResponse?.error || displayContent;
              const errorMessage = createAndDispatchMessage(ERROR, errorMsg);
              updatedMessages = [...state.chat.messages, newMessage, errorMessage];
            }
          } catch (e) {
            console.log("Error while parsing charts response", e);
          }
        } else if (!isChartResponseReceived) {
          dispatch({
            type: actionConstants.SET_LAST_RAG_RESPONSE,
            payload: streamMessage?.content as string,
          });
          updatedMessages = [...state.chat.messages, newMessage, streamMessage];
        }
      }
      
      if (updatedMessages.length > 0 && updatedMessages[updatedMessages.length - 1]?.role !== ERROR) {
        saveToDB(updatedMessages, conversationId, isChatReq);
      }
    } catch (e) {
      console.error("Error in makeApiRequestWithCosmosDB:", e);
      
      if (abortController.signal.aborted) {
        updatedMessages = streamMessage.content
          ? [...state.chat.messages, newMessage, streamMessage]
          : [...state.chat.messages, newMessage];
        
        saveToDB(updatedMessages, conversationId, 'error');
      } else if (e instanceof Error) {
        alert(e.message);
      } else {
        alert("An error occurred. Please try again. If the problem persists, please contact the site administrator.");
      }
    } finally {
      dispatch({
        type: actionConstants.UPDATE_GENERATING_RESPONSE_FLAG,
        payload: false,
      });
      dispatch({
        type: actionConstants.UPDATE_STREAMING_FLAG,
        payload: false,
      });
      abortController.abort();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // Disable enter key if generating response or history update API is pending
      if (generatingResponse || state.chatHistory.isHistoryUpdateAPIPending) {
        return;
      }
      const conversationId =
        state?.selectedConversationId || state.generatedConversationId;
      if (userMessage) {
        makeApiRequestWithCosmosDB(userMessage, conversationId);
      }
      if (questionInputRef?.current) {
        questionInputRef?.current.focus();
      }
    }
  };

  const onClickSend = () => {
    // Disable send button if generating response or history update API is pending
    if (generatingResponse || state.chatHistory.isHistoryUpdateAPIPending) {
      return;
    }
    const conversationId =
      state?.selectedConversationId || state.generatedConversationId;
    if (userMessage) {
      makeApiRequestWithCosmosDB(userMessage, conversationId);
    }
    if (questionInputRef?.current) {
      questionInputRef?.current.focus();
    }
  };

  const setUserMessage = (value: string) => {
    dispatch({ type: actionConstants.UPDATE_USER_MESSAGE, payload: value });
  };

  const onNewConversation = () => {
    dispatch({ type: actionConstants.NEW_CONVERSATION_START });
    dispatch({  type: actionConstants.UPDATE_CITATION,payload: { activeCitation: null, showCitation: false }})
  };
  const { messages } = state.chat;
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
        {Boolean(state.chatHistory?.isFetchingConvMessages) && (
          <div>
            <Spinner
              size={SpinnerSize.small}
              aria-label="Fetching Chat messages"
            />
          </div>
        )}
        {!Boolean(state.chatHistory?.isFetchingConvMessages) &&
          messages.length === 0 && (
            <div className="initial-msg">
              {/* <SparkleRegular fontSize={32} /> */}
              <h2>✨</h2>
              <Subtitle2>Start Chatting</Subtitle2>
              <Body1 style={{ textAlign: "center" }}>
                {chatLandingText}
              </Body1>
            </div>
          )}
        {!Boolean(state.chatHistory?.isFetchingConvMessages) &&
          messages.map((msg, index) => {
           
            return (
            <div key={index} className={`chat-message ${msg.role}`}>
              {(() => {
                const isLastAssistantMessage = msg.role === "assistant" && index === messages.length - 1;
                
                // Handle user messages
                if (msg.role === "user" && typeof msg.content === "string") {
                  if (msg.content === "show in a graph by default") return null;
                  return (
                    <div className="user-message">
                      <span>{msg.content}</span>
                    </div>
                  );
                }

                if (msg.role === "assistant" && typeof msg.content === "object" && msg.content !== null) {
                  if ("type" in msg.content && "data" in msg.content) {
                    
                    try {
                      return (
                        <div className="assistant-message chart-message">
                          <ChatChart chartContent={msg.content as ChartDataResponse} />
                          <div className="answerDisclaimerContainer">
                            <span className="answerDisclaimer">
                              AI-generated content may be incorrect
                            </span>
                          </div>
                        </div>
                      );
                    } catch (e) {
                      console.error("Chart rendering error:", e);
                      return (
                        <div className="assistant-message error-message">
                            ⚠️ Sorry, we couldn’t display the chart for this response.
                        </div>
                      );
                    }
                  }
                }

                                // Handle error messages
                if (msg.role === "error" && typeof msg.content === "string") {
                  return (
                    <div className="assistant-message error-message">
                      <p>{msg.content}</p>
                      <div className="answerDisclaimerContainer">
                        <span className="answerDisclaimer">
                          AI-generated content may be incorrect
                        </span>
                      </div>
                    </div>
                  );
                }

                // Handle assistant messages - string content (text, lists, tables, or stringified charts)
                if (msg.role === "assistant" && typeof msg.content === "string") {
                  // Try parsing as JSON to detect charts
                  let parsedContent = null;
                  try {
                    parsedContent = JSON.parse(msg.content);
                  } catch {
                    // Not JSON - treat as plain text
                    parsedContent = null;
                  }

                  // If parsed successfully and it's a chart object
                  if (parsedContent && typeof parsedContent === "object") {
                    let chartData = null;
                    
                    // SCENARIO 1: Direct chart object {type, data, options}
                    if ("type" in parsedContent && "data" in parsedContent) {
                      chartData = parsedContent;
                    }
                    // SCENARIO 2: Wrapped chart {"answer": {type, data, options}}
                    else if ("answer" in parsedContent) {
                      const answer = parsedContent.answer;
                      if (answer && typeof answer === "object" && "type" in answer && "data" in answer) {
                        chartData = answer;
                      } else {
                        console.warn(`⚠️ Answer exists but is not a valid chart:`, answer);
                      }
                    }
                    
                    // Render chart if valid chartData was found
                    if (chartData && "type" in chartData && "data" in chartData) {
                      try {
                        return (
                          <div className="assistant-message chart-message">
                            <ChatChart chartContent={chartData} />
                            <div className="answerDisclaimerContainer">
                              <span className="answerDisclaimer">
                                AI-generated content may be incorrect
                              </span>
                            </div>
                          </div>
                        );
                      } catch (e) {
                        console.error("❌ Chart rendering error:", e);
                        return (
                          <div className="assistant-message error-message">
                            ⚠️ Sorry, we couldn’t display the chart for this response.
                          </div>
                        );
                      }
                    }
                  }

                  // Plain text message (most common case)
                  const containsHTML = /<\/?[a-z][\s\S]*>/i.test(msg.content);
                  
                  return (
                    <div className="assistant-message">
                      {containsHTML ? (
                        <div 
                          dangerouslySetInnerHTML={{ __html: msg.content }}
                          className="html-content"
                        />
                      ) : (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, supersub]}
                          children={msg.content}
                        />
                      )}
                      
                      {/* Citation Loader: Show only while citations are fetching */}
                      {isLastAssistantMessage && generatingResponse ? (
                        <div className="typing-indicator">
                          <span className="dot"></span>
                          <span className="dot"></span>
                          <span className="dot"></span>
                        </div>
                      ) : (
                        <Citations
                          answer={{
                            answer: msg.content,
                            citations:
                              msg.role === "assistant"
                                ? parseCitationFromMessage(msg.citations)
                                : [],
                          }}
                          index={index}
                        />
                      )}

                      <div className="answerDisclaimerContainer">
                        <span className="answerDisclaimer">
                          AI-generated content may be incorrect
                        </span>
                      </div>
                    </div>
                  );
                }

                // Fallback for unexpected content types
                console.warn(`Unhandled message at index ${index}:`, { role: msg.role, contentType: typeof msg.content });
                return null;
              })()}
            </div>
            );
          })}
        {((generatingResponse && !state.chat.isStreamingInProgress) || isChartLoading)  && (
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
          disabled={
            generatingResponse || state.chatHistory.isHistoryUpdateAPIPending
          }
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
            disabled={
              generatingResponse ||
              !userMessage.trim() ||
              state.chatHistory.isHistoryUpdateAPIPending
            }
            className="send-button"
            aria-disabled={
              generatingResponse ||
              !userMessage ||
              state.chatHistory.isHistoryUpdateAPIPending
            }
            title="Send Question"
          />
        </div>
      </div>
    </div>
  );
};

export default Chat;
