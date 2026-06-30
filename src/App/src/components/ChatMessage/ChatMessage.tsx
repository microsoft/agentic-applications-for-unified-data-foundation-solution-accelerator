import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from "remark-supersub";
import ChatChart from "../ChatChart/ChatChart";
import Citations from "../Citations/Citations";
import { ChatMessage as ChatMessageType, ChartDataResponse } from "../../types/AppTypes";

interface ChatMessageProps {
  message: ChatMessageType;
  index: number;
  isLastAssistantMessage: boolean;
  generatingResponse: boolean;
  parseCitationFromMessage: (citations: any) => any[];
}

const ChatMessage: React.FC<ChatMessageProps> = memo(({
  message,
  index,
  isLastAssistantMessage,
  generatingResponse,
  parseCitationFromMessage
}) => {
  // Handle user messages
  if (message.role === "user" && typeof message.content === "string") {
    if (message.content === "show in a graph by default") return null;
    return (
      <div className="user-message">
        <span>{message.content}</span>
      </div>
    );
  }

  // Handle chart messages - object content
  if (message.role === "assistant" && typeof message.content === "object" && message.content !== null) {
    if (("type" in message.content || "chartType" in message.content) && "data" in message.content) {
      try {
        return (
          <div className="assistant-message chart-message">
            <ChatChart chartContent={message.content as ChartDataResponse} />
            <div className="answerDisclaimerContainer">
              <span className="answerDisclaimer">
                AI-generated content may be incorrect
              </span>
            </div>
          </div>
        );
      } catch {
        return (
          <div className="assistant-message error-message">
            ⚠️ Sorry, we couldn't display the chart for this response.
          </div>
        );
      }
    }
  }

  // Handle error messages
  if (message.role === "error" && typeof message.content === "string") {
    return (
      <div className="assistant-message error-message">
        <p>{message.content}</p>
        <div className="answerDisclaimerContainer">
          <span className="answerDisclaimer">
            AI-generated content may be incorrect
          </span>
        </div>
      </div>
    );
  }

  // Handle assistant messages - string content (text, lists, tables, or stringified charts)
  if (message.role === "assistant" && typeof message.content === "string") {
    // Try parsing as JSON to detect charts
    let parsedContent = null;
    try {
      parsedContent = JSON.parse(message.content);
    } catch {
      // Not JSON - treat as plain text
      parsedContent = null;
    }

    // If parsed successfully and it's a chart object
    if (parsedContent && typeof parsedContent === "object") {
      let chartData = null;
      
      // SCENARIO 1: Direct chart object {type, data, options}
      if (("type" in parsedContent || "chartType" in parsedContent) && "data" in parsedContent) {
        chartData = parsedContent;
      }
      // SCENARIO 2: Wrapped chart {"answer": {type, data, options}}
      else if ("answer" in parsedContent) {
        const answer = parsedContent.answer;
        if (answer && typeof answer === "object" && ("type" in answer || "chartType" in answer) && "data" in answer) {
          chartData = answer;
        }
      }

      // Render chart if valid chartData was found
      if (chartData && ("type" in chartData || "chartType" in chartData) && "data" in chartData) {
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
        } catch {
          return (
            <div className="assistant-message error-message">
              ⚠️ Sorry, we couldn't display the chart for this response.
            </div>
          );
        }
      }
    }

    // Plain text message (most common case)
    const containsHTML = /<\/?[a-z][\s\S]*>/i.test(message.content);
    
    return (
      <div className="assistant-message">
        {containsHTML ? (
          <div 
            dangerouslySetInnerHTML={{ __html: message.content }}
            className="html-content"
          />
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, supersub]}
            children={message.content}
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
              answer: message.content,
              citations:
                message.role === "assistant"
                  ? parseCitationFromMessage(message.citations)
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
  return null;
});

ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;
