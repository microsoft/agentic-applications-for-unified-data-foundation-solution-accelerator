using System.Data;
using System.Data.Common;
using System.Data.Odbc;
using CsApi.Models;
using System.Text.Json;

namespace CsApi.Repositories;

public interface ISqlConversationRepository
{
    Task<(string ConversationId, bool IsNewConversation)> EnsureConversationAsync(string? userId, string? conversationId, string title, CancellationToken ct);
    Task UpdateConversationTitleAsync(string? userId, string conversationId, string title, CancellationToken ct);
    Task AddMessageAsync(string? userId, string conversationId, ChatMessage message, CancellationToken ct);
    Task<IReadOnlyList<ConversationSummary>> ListAsync(string? userId, int offset, int limit, string sortOrder, CancellationToken ct);
    Task<IReadOnlyList<ChatMessage>> ReadAsync(string? userId, string conversationId, string sortOrder, CancellationToken ct);
    Task<bool?> DeleteAsync(string? userId, string conversationId, CancellationToken ct);
    Task<int?> DeleteAllAsync(string? userId, CancellationToken ct);
    Task<bool?> RenameAsync(string? userId, string conversationId, string title, CancellationToken ct);
    Task<string> ExecuteChatQuery(string query, CancellationToken ct);
}

public class SqlConversationRepository : ISqlConversationRepository
{
    private readonly IConfiguration _config;
    private readonly ILogger<SqlConversationRepository> _logger;

    public SqlConversationRepository(IConfiguration config, ILogger<SqlConversationRepository> logger)
    { 
        _config = config; 
        _logger = logger; 
    }

    private async Task<IDbConnection> CreateConnectionAsync()
    {
        const int maxRetries = 3;
        for (int attempt = 1; attempt <= maxRetries; attempt++)
        {
            try
            {
                return await CreateConnectionCoreAsync();
            }
            catch (Exception ex)
            {
                _logger.LogWarning("Database connection attempt {Attempt}/{MaxRetries} failed: {Error}", attempt, maxRetries, ex.Message);
                if (attempt < maxRetries)
                {
                    var delay = TimeSpan.FromSeconds(Math.Pow(2, attempt)); // Exponential backoff: 2s, 4s
                    await Task.Delay(delay);
                }
                else
                {
                    _logger.LogError(ex, "Failed to establish database connection after {MaxRetries} attempts", maxRetries);
                    throw;
                }
            }
        }
        // Should never reach here, but satisfies compiler
        throw new InvalidOperationException("Failed to establish database connection.");
    }

    private async Task<IDbConnection> CreateConnectionCoreAsync()
    {
        var appEnv = (_config["APP_ENV"] ?? "prod").ToLower();

        // In prod, use FABRIC_SQL_CONNECTION_STRING directly
        if (appEnv == "prod")
        {
            var connectionString = _config["FABRIC_SQL_CONNECTION_STRING"];

            if (string.IsNullOrWhiteSpace(connectionString))
            {
                throw new InvalidOperationException("FABRIC_SQL_CONNECTION_STRING is not configured.");
            }

            _logger.LogInformation("Connecting to Fabric SQL with ODBC");

            var conn = new OdbcConnection(connectionString);
            await conn.OpenAsync();
            return conn;
        }

        // In dev, use ODBC with ActiveDirectoryInteractive authentication
        var db = _config["FABRIC_SQL_DATABASE"]?.Trim(' ', '{', '}');
        var server = _config["FABRIC_SQL_SERVER"];

        var devConnectionString =
            "Driver={ODBC Driver 18 for SQL Server};" +
            $"Server={server};" +
            $"Database={db};" +
            "Authentication=ActiveDirectoryInteractive;" +
            "Encrypt=yes;" +
            "TrustServerCertificate=no;";

        _logger.LogInformation("Connecting to Fabric SQL with ODBC + ActiveDirectoryInteractive authentication (dev)");

        var conn2 = new OdbcConnection(devConnectionString);
        await conn2.OpenAsync();
        return conn2;
    }


    public async Task<(string ConversationId, bool IsNewConversation)> EnsureConversationAsync(string? userId, string? conversationId, string title, CancellationToken ct)
    {
        var id = conversationId ?? Guid.NewGuid().ToString();
        using var conn = await CreateConnectionAsync();
        
        _logger.LogInformation("EnsureConversationAsync - Input: userId={UserId}, conversationId={ConversationId}, generatedId={GeneratedId}", 
            userId ?? "NULL", conversationId ?? "NULL", id);
        
        // Check if conversation exists
        const string existsSql = "SELECT userId FROM hst_conversations WHERE conversation_id=?";
        using (var check = new OdbcCommand(existsSql, (OdbcConnection)conn))
        {
            check.Parameters.AddWithValue("", id);
            
            var result = check.ExecuteScalar();
            if (result != null)
            {
                 return (id, false); // Conversation exists and user has permission
            }
        }
        
        // Conversation doesn't exist, create it
        _logger.LogInformation("EnsureConversationAsync - Creating NEW conversation with id={ConversationId}", id);
        const string insertSql = "INSERT INTO hst_conversations (userId, conversation_id, title, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?)";
        var now = DateTime.UtcNow.ToString("o");
        using (var cmd = new OdbcCommand(insertSql, (OdbcConnection)conn))
        {
            cmd.Parameters.AddWithValue("", userId ?? string.Empty);
            cmd.Parameters.AddWithValue("", id);
            cmd.Parameters.AddWithValue("", title ?? string.Empty);
            cmd.Parameters.AddWithValue("", now);
            cmd.Parameters.AddWithValue("", now);
            var rowsAffected = cmd.ExecuteNonQuery();
            _logger.LogInformation("EnsureConversationAsync - Created conversation, rows affected: {RowsAffected}", rowsAffected);
        }
        return (id, true); // New conversation created
    }

    public async Task UpdateConversationTitleAsync(string? userId, string conversationId, string title, CancellationToken ct)
    {
        using var conn = await CreateConnectionAsync();
        string sql;
        
        if (!string.IsNullOrEmpty(userId))
        {
            sql = "UPDATE hst_conversations SET title=?, updatedAt=? WHERE userId=? AND conversation_id=?";
            using var cmd = new OdbcCommand(sql, (OdbcConnection)conn);
            cmd.Parameters.AddWithValue("", title);
            cmd.Parameters.AddWithValue("", DateTime.UtcNow.ToString("o"));
            cmd.Parameters.AddWithValue("", userId);
            cmd.Parameters.AddWithValue("", conversationId);
            cmd.ExecuteNonQuery();
        }
        else
        {
            sql = "UPDATE hst_conversations SET title=?, updatedAt=? WHERE conversation_id=?";
            using var cmd = new OdbcCommand(sql, (OdbcConnection)conn);
            cmd.Parameters.AddWithValue("", title);
            cmd.Parameters.AddWithValue("", DateTime.UtcNow.ToString("o"));
            cmd.Parameters.AddWithValue("", conversationId);
            cmd.ExecuteNonQuery();
        }
    }

    public async Task AddMessageAsync(string? userId, string conversationId, ChatMessage message, CancellationToken ct)
    {
        var now = DateTime.UtcNow.ToString("o");
        using var conn = await CreateConnectionAsync();
        
        // Get citations as JSON string for storage (matches Python behavior)
        var citationsJson = message.GetCitationsAsJsonString();
        
        // Get content as JSON string for storage - this preserves chart data structure
        var contentJson = message.GetContentAsJsonString();
        
        if (!string.IsNullOrEmpty(userId))
        {
            // INSERT message
            var insertSql = "INSERT INTO hst_conversation_messages (userId, conversation_id, role, content_id, content, citations, feedback, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";
            using (var insertCmd = new OdbcCommand(insertSql, (OdbcConnection)conn))
            {
                insertCmd.Parameters.AddWithValue("", userId);
                insertCmd.Parameters.AddWithValue("", conversationId);
                insertCmd.Parameters.AddWithValue("", message.Role);
                insertCmd.Parameters.AddWithValue("", message.Id);
                insertCmd.Parameters.AddWithValue("", contentJson);
                insertCmd.Parameters.AddWithValue("", citationsJson);
                insertCmd.Parameters.AddWithValue("", message.Feedback ?? string.Empty);
                insertCmd.Parameters.AddWithValue("", now);
                insertCmd.Parameters.AddWithValue("", now);
                insertCmd.ExecuteNonQuery();
            }
            // UPDATE conversation timestamp
            using (var updateCmd = new OdbcCommand("UPDATE hst_conversations SET updatedAt=? WHERE conversation_id=?", (OdbcConnection)conn))
            {
                updateCmd.Parameters.AddWithValue("", now);
                updateCmd.Parameters.AddWithValue("", conversationId);
                updateCmd.ExecuteNonQuery();
            }
        }
        else
        {
            // INSERT message
            var insertSql = "INSERT INTO hst_conversation_messages (conversation_id, role, content_id, content, citations, feedback, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
            using (var insertCmd = new OdbcCommand(insertSql, (OdbcConnection)conn))
            {
                insertCmd.Parameters.AddWithValue("", conversationId);
                insertCmd.Parameters.AddWithValue("", message.Role);
                insertCmd.Parameters.AddWithValue("", message.Id);
                insertCmd.Parameters.AddWithValue("", contentJson);
                insertCmd.Parameters.AddWithValue("", citationsJson);
                insertCmd.Parameters.AddWithValue("", message.Feedback ?? string.Empty);
                insertCmd.Parameters.AddWithValue("", now);
                insertCmd.Parameters.AddWithValue("", now);
                insertCmd.ExecuteNonQuery();
            }
            // UPDATE conversation timestamp
            using (var updateCmd = new OdbcCommand("UPDATE hst_conversations SET updatedAt=? WHERE conversation_id=?", (OdbcConnection)conn))
            {
                updateCmd.Parameters.AddWithValue("", now);
                updateCmd.Parameters.AddWithValue("", conversationId);
                updateCmd.ExecuteNonQuery();
            }
        }
    }

    public async Task<IReadOnlyList<ConversationSummary>> ListAsync(string? userId, int offset, int limit, string sortOrder, CancellationToken ct)
    {
        var list = new List<ConversationSummary>();
        try
        {
            var order = sortOrder.Equals("asc", StringComparison.OrdinalIgnoreCase) ? "ASC" : "DESC";
            using var conn = await CreateConnectionAsync();
            string sql;
            bool filterByUser = !string.IsNullOrEmpty(userId);
            // REDUNDANT: Detailed user listing logging
            // Console.WriteLine($"Listing conversations for user '{userId}' (filterByUser={filterByUser})");
            sql = filterByUser
                ? $"SELECT conversation_id, title, createdAt, updatedAt FROM hst_conversations WHERE userId=? ORDER BY updatedAt {order} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
                : $"SELECT conversation_id, title, createdAt, updatedAt FROM hst_conversations ORDER BY updatedAt {order} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY";
            using (var cmd = new OdbcCommand(sql, (OdbcConnection)conn))
            {
                if (filterByUser)
                    cmd.Parameters.AddWithValue("", userId);
                cmd.Parameters.AddWithValue("", offset);
                cmd.Parameters.AddWithValue("", limit);
                using var reader = cmd.ExecuteReader();
                while (reader.Read())
                {
                    var title = reader.IsDBNull(reader.GetOrdinal("title")) ? "New Conversation" : reader.GetString("title");
                    var createdAt = reader.IsDBNull(reader.GetOrdinal("createdAt")) ? DateTime.UtcNow : reader.GetDateTime("createdAt");
                    var updatedAt = reader.IsDBNull(reader.GetOrdinal("updatedAt")) ? DateTime.UtcNow : reader.GetDateTime("updatedAt");
                    
                    // Ensure title is not empty
                    if (string.IsNullOrWhiteSpace(title))
                    {
                        title = "New Conversation";
                    }
                    
                    list.Add(new ConversationSummary
                    {
                        ConversationId = reader.GetString("conversation_id"),
                        Title = title,
                        CreatedAt = createdAt,
                        UpdatedAt = updatedAt
                    });
                }
            }
            // REDUNDANT: Verbose logging can be reduced in production
            // Console.WriteLine($"Retrieved {list.Count} conversations from database");
            // foreach (var conv in list)
            // {
            //     Console.WriteLine($"  - {conv.ConversationId}: '{conv.Title}' (user: {conv.UserId}) [created: {conv.CreatedAt}, updated: {conv.UpdatedAt}]");
            // }
        }
        catch (OdbcException ex)
        {
            _logger.LogError(ex, "SQL error listing conversations for user {UserId}", userId);
        }
        catch (DbException ex)
        {
            _logger.LogError(ex, "Database error listing conversations for user {UserId}", userId);
        }
        catch (TimeoutException ex)
        {
            _logger.LogWarning(ex, "Timeout listing conversations for user {UserId}", userId);
        }
        catch (OperationCanceledException)
        {
            // Request was cancelled, no logging needed
        }
        catch (Exception ex) when (ex is not OperationCanceledException && ex is not OdbcException && ex is not DbException && ex is not TimeoutException)
        {
            _logger.LogError(ex, "Unexpected error listing conversations for user {UserId}", userId);
            throw;
        }
        return list;
    }

    public async Task<IReadOnlyList<ChatMessage>> ReadAsync(string? userId, string conversationId, string sortOrder, CancellationToken ct)
    {
        var order = sortOrder.Equals("asc", StringComparison.OrdinalIgnoreCase) ? "ASC" : "DESC";
        string sql;
        bool filterByUser = !string.IsNullOrEmpty(userId);
        // REDUNDANT: Detailed message reading logging
        // Console.WriteLine($"Reading messages for user '{userId}' and conversation '{conversationId}' (filterByUser={filterByUser})");
        if (string.IsNullOrEmpty(conversationId))
            return new List<ChatMessage>();
        sql = filterByUser
            ? $"SELECT role, content, citations, feedback FROM hst_conversation_messages WHERE userId=? AND conversation_id=? ORDER BY updatedAt {order}"
            : $"SELECT role, content, citations, feedback FROM hst_conversation_messages WHERE conversation_id=? ORDER BY updatedAt {order}";
        var list = new List<ChatMessage>();
        using var conn = await CreateConnectionAsync();
        using (var cmd = new OdbcCommand(sql, (OdbcConnection)conn))
        {
            if (filterByUser)
                cmd.Parameters.AddWithValue("", userId);
            cmd.Parameters.AddWithValue("", conversationId);
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var role = reader.IsDBNull(reader.GetOrdinal("role")) ? null : reader.GetString("role");
                var contentRaw = reader.IsDBNull(reader.GetOrdinal("content")) ? null : reader.GetString("content");
                var citationsStr = reader.IsDBNull(reader.GetOrdinal("citations")) ? null : reader.GetString("citations");
                var feedback = reader.IsDBNull(reader.GetOrdinal("feedback")) ? null : reader.GetString("feedback");
                
                // Parse content from JSON string back to JsonElement (matches Python behavior)
                // This is crucial for chart data to be properly structured instead of string
                JsonElement content = JsonSerializer.SerializeToElement(string.Empty);
                if (!string.IsNullOrWhiteSpace(contentRaw))
                {
                    try 
                    { 
                        // Try to deserialize content as JSON first
                        content = JsonSerializer.Deserialize<JsonElement>(contentRaw);
                    } 
                    catch (JsonException)
                    { 
                        // If parsing fails, treat as string
                        content = JsonSerializer.SerializeToElement(contentRaw);
                    }
                }
                
                // Parse citations as JsonElement to maintain flexibility (matches Python behavior)
                JsonElement? citations = null;
                if (!string.IsNullOrWhiteSpace(citationsStr))
                {
                    try 
                    { 
                        citations = JsonSerializer.Deserialize<JsonElement>(citationsStr);
                    } 
                    catch (JsonException)
                    { 
                        // If parsing fails, treat as null
                        citations = null;
                    }
                    catch (NotSupportedException)
                    {
                        // Handle cases where the data type is not supported for deserialization
                        citations = null;
                    }
                }
                
                list.Add(new ChatMessage
                {
                    Role = role ?? string.Empty,
                    Content = content,
                    Citations = citations,
                    Feedback = feedback ?? string.Empty
                });
            }
        }
        // REDUNDANT: Message count logging
        // Console.WriteLine($"Read {list.Count} messages for conversation '{conversationId}'");
        return list;
    }

    public async Task<bool?> DeleteAsync(string? userId, string conversationId, CancellationToken ct)
    {
        // 1. Check if conversation exists
        const string checkSql = "SELECT userId FROM hst_conversations WHERE conversation_id=?";
        using var conn = await CreateConnectionAsync();
        string? foundUserId;
        
        using (var checkCmd = new OdbcCommand(checkSql, (OdbcConnection)conn))
        {
            checkCmd.Parameters.AddWithValue("", conversationId);
            var result = checkCmd.ExecuteScalar();
            if (result == null)
                return null; // Not found
            foundUserId = result.ToString();
        }

        // 2. If userId is provided, check permission
        if (!string.IsNullOrEmpty(userId) && foundUserId != userId)
            return false; // Permission denied

        // 3. Delete conversation and messages
        string deleteMessagesSql = !string.IsNullOrEmpty(userId)
            ? "DELETE FROM hst_conversation_messages WHERE userId=? AND conversation_id=?"
            : "DELETE FROM hst_conversation_messages WHERE conversation_id=?";
        string deleteConversationSql = !string.IsNullOrEmpty(userId)
            ? "DELETE FROM hst_conversations WHERE userId=? AND conversation_id=?"
            : "DELETE FROM hst_conversations WHERE conversation_id=?";

        using var delMsgCmd = new OdbcCommand(deleteMessagesSql, (OdbcConnection)conn);
        using var delConvCmd = new OdbcCommand(deleteConversationSql, (OdbcConnection)conn);

        if (!string.IsNullOrEmpty(userId))
        {
            delMsgCmd.Parameters.AddWithValue("", userId);
            delConvCmd.Parameters.AddWithValue("", userId);
        }
        delMsgCmd.Parameters.AddWithValue("", conversationId);
        delConvCmd.Parameters.AddWithValue("", conversationId);

        delMsgCmd.ExecuteNonQuery();
        var rows = delConvCmd.ExecuteNonQuery();
        return rows > 0;
    }

    public async Task<int?> DeleteAllAsync(string? userId, CancellationToken ct)
    {
        using var conn = await CreateConnectionAsync();
        
        // If userId is provided, delete only that user's conversations
        // If userId is null/empty, allow global delete (all conversations)
        string deleteMessagesSql = !string.IsNullOrEmpty(userId)
            ? "DELETE FROM hst_conversation_messages WHERE userId=?"
            : "DELETE FROM hst_conversation_messages";
        string deleteConversationsSql = !string.IsNullOrEmpty(userId)
            ? "DELETE FROM hst_conversations WHERE userId=?"
            : "DELETE FROM hst_conversations";

        using var delMsgCmd = new OdbcCommand(deleteMessagesSql, (OdbcConnection)conn);
        using var delConvCmd = new OdbcCommand(deleteConversationsSql, (OdbcConnection)conn);

        if (!string.IsNullOrEmpty(userId))
        {
            delMsgCmd.Parameters.AddWithValue("", userId);
            delConvCmd.Parameters.AddWithValue("", userId);
        }

        // Delete messages first, then conversations
        delMsgCmd.ExecuteNonQuery();
        var conversationsDeleted = delConvCmd.ExecuteNonQuery();

        return conversationsDeleted;
    }

    public async Task<bool?> RenameAsync(string? userId, string conversationId, string title, CancellationToken ct)
    {
        // 1. Check if conversation exists
        const string checkSql = "SELECT userId FROM hst_conversations WHERE conversation_id=?";
        using var conn = await CreateConnectionAsync();
        string? foundUserId;
        using (var checkCmd = new OdbcCommand(checkSql, (OdbcConnection)conn))
        {
            checkCmd.Parameters.AddWithValue("", conversationId);
            var result = checkCmd.ExecuteScalar();
            if (result == null)
                return null; // Not found
            foundUserId = result.ToString();
        }

        // 2. If userId is provided, check permission
        if (!string.IsNullOrEmpty(userId) && foundUserId != userId)
            return false; // Permission denied

        // 3. Update title
        string updateSql = !string.IsNullOrEmpty(userId)
            ? "UPDATE hst_conversations SET title=?, updatedAt=? WHERE userId=? AND conversation_id=?"
            : "UPDATE hst_conversations SET title=?, updatedAt=? WHERE conversation_id=?";

        using var updateCmd = new OdbcCommand(updateSql, (OdbcConnection)conn);
        updateCmd.Parameters.AddWithValue("", title);
        updateCmd.Parameters.AddWithValue("", DateTime.UtcNow.ToString("o"));
        if (!string.IsNullOrEmpty(userId))
        {
            updateCmd.Parameters.AddWithValue("", userId);
        }
        updateCmd.Parameters.AddWithValue("", conversationId);

        var rows = updateCmd.ExecuteNonQuery();
        return rows > 0;
    }

    public async Task<string> ExecuteChatQuery(string query, CancellationToken ct)
    {
        _logger.LogInformation("Chat Agent - Executing SQL query: {Query}", query);
        var results = new List<Dictionary<string, object?>>();
        using var conn = await CreateConnectionAsync();
        using var cmd = new OdbcCommand(query, (OdbcConnection)conn);
        try
        {
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var row = new Dictionary<string, object?>();
                for (int i = 0; i < reader.FieldCount; i++)
                {
                    var colName = reader.GetName(i);
                    var value = reader.IsDBNull(i) ? null : reader.GetValue(i);
                
                    // Handle data type conversions to match Python SqlQueryTool behavior
                    if (value != null)
                    {
                        // Convert DateTime, DateOnly, and TimeOnly to ISO format string like Python
                        if (value is DateTime dateTime)
                        {
                            row[colName] = dateTime.ToString("O"); // ISO 8601 format (matches Python .isoformat())
                        }
                        else if (value is DateOnly dateOnly)
                        {
                            row[colName] = dateOnly.ToString("yyyy-MM-dd"); // ISO date format
                        }
                        else if (value is TimeOnly timeOnly)
                        {
                            row[colName] = timeOnly.ToString("HH:mm:ss"); // ISO time format
                        }
                        // Convert Decimal to double like Python converts to float
                        else if (value is decimal decimalValue)
                        {
                            row[colName] = (double)decimalValue;
                        }
                        // Handle other numeric types consistently
                        else if (value is float floatValue)
                        {
                            row[colName] = (double)floatValue;
                        }
                        // Handle GUID as string for JSON serialization
                        else if (value is Guid guidValue)
                        {
                            row[colName] = guidValue.ToString();
                        }
                        else
                        {
                            row[colName] = value;
                        }
                    }
                    else
                    {
                        row[colName] = null;
                    }
                }
                results.Add(row);
            }
        }
        catch (OperationCanceledException)
        {
            // Preserve cancellation semantics for callers
            throw;
        }
        catch (OdbcException ex)
        {
            _logger.LogError(ex, "SQL error executing chat query");
            throw;
        }
        catch (Exception ex) when (ex is not OperationCanceledException && ex is not OdbcException)
        {
            _logger.LogError(ex, "Chat Agent - Error executing SQL query: {Query}", query);
            throw;
        }
        if (results.Count == 0)
        {
            _logger.LogInformation("Chat Agent - SQL query returned no results.");
            return "No results found.";            
        }
        var json = JsonSerializer.Serialize(results);
        _logger.LogInformation("Chat Agent - Result of SQL query: {Result}", json);
        return json;
    }
}
