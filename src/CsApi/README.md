# CsApi

ASP.NET Core Web API parity layer for the original FastAPI backend. Updated to use SQL (`historyfab` endpoints) and streaming JSON-lines for chat.

## Implemented Endpoints
`/api/chat` (POST, streaming JSON lines)
`/api/layout-config` (GET placeholder)
`/api/display-chart-default` (GET placeholder)
`/api/fetch-azure-search-content` (POST placeholder)
`/historyfab/list|read|delete|delete_all|rename|update` (SQL backed)

## Persistence (`historyfab` SQL)
Uses tables expected by the Python version:
`hst_conversations(userId, conversation_id, title, createdAt, updatedAt)`
`hst_conversation_messages(userId, conversation_id, role, content_id, content, citations, feedback, createdAt, updatedAt)`

Provide either:
`FABRIC_SQL_CONNECTION_STRING` (full connection string) OR
`FABRIC_SQL_SERVER` + `FABRIC_SQL_DATABASE` (Managed Identity / Azure AD auth).

## Streaming Behaviour
`/api/chat` returns `application/json-lines` with envelopes like:
```
{"id":"<conversationId>","model":"echo-model","created":1736030000,"choices":[{"messages":[{"role":"assistant","content":"partial"}],"delta":{"role":"assistant","content":"partial"}}]}
```
Double newline delimits chunks; UI can append as they arrive (mirrors FastAPI progressive updates).

## Not Implemented
- Cosmos `/history` endpoints (explicitly excluded).
- RAG / agent logic (current model echoes query text).

## Auth Placeholder
User id resolved from header `x-ms-client-principal-id`.

## Run
```
dotnet restore
dotnet run --project src/api/cs-api/CsApi/CsApi.csproj
```
Service listens on http://localhost:8000.

## Future Enhancements
- Replace echo logic with real Azure AI/Agents streaming.
- Add unit tests for streaming and SQL history operations.
- Introduce telemetry (App Insights) and fuller error parity.
