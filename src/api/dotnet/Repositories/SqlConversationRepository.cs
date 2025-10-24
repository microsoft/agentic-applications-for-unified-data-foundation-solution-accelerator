using System.Data;
using Microsoft.Data.SqlClient;
using CsApi.Models;
using Azure.Identity;
using Azure.Core;
using System.Threading.Tasks;
using System.Text.Json;

namespace CsApi.Repositories;

public interface ISqlConversationRepository
{
    Task<(string ConversationId, bool IsNewConversation)> EnsureConversationAsync(string userId, string? conversationId, string title, CancellationToken ct);
    Task UpdateConversationTitleAsync(string userId, string conversationId, string title, CancellationToken ct);
    Task AddMessageAsync(string userId, string conversationId, ChatMessage message, CancellationToken ct);
    Task<IReadOnlyList<ConversationSummary>> ListAsync(string userId, int offset, int limit, string sortOrder, CancellationToken ct);
    Task<IReadOnlyList<ChatMessage>> ReadAsync(string userId, string conversationId, string sortOrder, CancellationToken ct);
    Task<bool?> DeleteAsync(string userId, string conversationId, CancellationToken ct);
    Task<int?> DeleteAllAsync(string userId, CancellationToken ct);
    Task<bool?> RenameAsync(string userId, string conversationId, string title, CancellationToken ct);
    Task<string> ExecuteChatQuery(string query, CancellationToken ct);
}

public class SqlConversationRepository : ISqlConversationRepository
{
    private readonly IConfiguration _config;
    private readonly ILogger<SqlConversationRepository> _logger;

    public SqlConversationRepository(IConfiguration config, ILogger<SqlConversationRepository> logger)
    { _config = config; _logger = logger; }

    private async Task<IDbConnection> CreateConnectionAsync()
    {
        var appEnv = (_config["APP_ENV"] ?? "prod").ToLower();

        // In prod, fall back to connection string from config (if needed)
        if (appEnv == "prod")
        {
            var odbcCs = _config["FABRIC_SQL_CONNECTION_STRING"];
            
            // Convert ODBC connection string to SQL Server format
            var sqlCs = ConvertOdbcToSqlConnectionString(odbcCs);
            
            var sqlConn = new SqlConnection(sqlCs);
            await sqlConn.OpenAsync();
            // Console.WriteLine("✅ Connected to Fabric SQL using connection string."); // Verbose logging removed
            return sqlConn;
        }

        // In dev, use Azure AD authentication (no username/password required)
        var db = _config["FABRIC_SQL_DATABASE"]?.Trim(' ', '{', '}');
        var server = _config["FABRIC_SQL_SERVER"];

        // REDUNDANT: Verbose connection info logging
        // Console.WriteLine($"Using Azure CLI/Azure AD authentication for {server}, database {db}");

        var connectionString =
            $"Server=tcp:{server},1433;" +
            $"Database={db};" +
            "Encrypt=True;" +
            "TrustServerCertificate=False;";

        var credential = new DefaultAzureCredential();
        var token = await credential.GetTokenAsync(
            new TokenRequestContext(new[] { "https://database.windows.net/.default" }));

        var sqlConnWithToken = new SqlConnection(connectionString)
        {
            AccessToken = token.Token
        };

        await sqlConnWithToken.OpenAsync();
        // Console.WriteLine("✅ Connected to Fabric SQL using Azure Identity (no username/password)."); // Verbose logging removed

        return sqlConnWithToken;

    }


    public async Task<(string ConversationId, bool IsNewConversation)> EnsureConversationAsync(string userId, string? conversationId, string title, CancellationToken ct)
    {
        var id = conversationId ?? Guid.NewGuid().ToString();
        using var conn = await CreateConnectionAsync();
        
        _logger.LogInformation("EnsureConversationAsync - Input: userId={UserId}, conversationId={ConversationId}, generatedId={GeneratedId}", 
            userId ?? "NULL", conversationId ?? "NULL", id);
        
        // Check if conversation exists
        string existsSql;
        string foundUserId = null;
        
        // Only filter by userId if it's provided (not null/empty)
        if (!string.IsNullOrEmpty(userId))
        {
            existsSql = "SELECT userId FROM hst_conversations WHERE conversation_id=@c AND userId=@u";
        }
        else
        {
            existsSql = "SELECT userId FROM hst_conversations WHERE conversation_id=@c";
        }
        
        using (var check = new SqlCommand(existsSql, (SqlConnection)conn))
        {
            check.Parameters.Add(new SqlParameter("@c", id));
            if (!string.IsNullOrEmpty(userId))
            {
                check.Parameters.Add(new SqlParameter("@u", userId));
            }
            
            var result = check.ExecuteScalar();
            if (result != null)
            {
                foundUserId = result.ToString() ?? string.Empty;
                 return (id, false); // Conversation exists and user has permission
            }
        }
        
        // Conversation doesn't exist, create it
        _logger.LogInformation("EnsureConversationAsync - Creating NEW conversation with id={ConversationId}", id);
        const string insertSql = "INSERT INTO hst_conversations (userId, conversation_id, title, createdAt, updatedAt) VALUES (@u, @c, @t, @n, @n)";
        var now = DateTime.UtcNow.ToString("o");
        using (var cmd = new SqlCommand(insertSql, (SqlConnection)conn))
        {
            cmd.Parameters.Add(new SqlParameter("@u", userId ?? string.Empty));
            cmd.Parameters.Add(new SqlParameter("@c", id));
            cmd.Parameters.Add(new SqlParameter("@t", title ?? string.Empty));
            cmd.Parameters.Add(new SqlParameter("@n", now));
            var rowsAffected = cmd.ExecuteNonQuery();
            _logger.LogInformation("EnsureConversationAsync - Created conversation, rows affected: {RowsAffected}", rowsAffected);
        }
        return (id, true); // New conversation created
    }

    public async Task UpdateConversationTitleAsync(string userId, string conversationId, string title, CancellationToken ct)
    {
        using var conn = await CreateConnectionAsync();
        string sql;
        
        if (!string.IsNullOrEmpty(userId))
        {
            sql = "UPDATE hst_conversations SET title=@t, updatedAt=@n WHERE userId=@u AND conversation_id=@c";
            using var cmd = new SqlCommand(sql, (SqlConnection)conn);
            cmd.Parameters.AddWithValue("@t", title);
            cmd.Parameters.AddWithValue("@n", DateTime.UtcNow.ToString("o"));
            cmd.Parameters.AddWithValue("@u", userId);
            cmd.Parameters.AddWithValue("@c", conversationId);
            cmd.ExecuteNonQuery();
        }
        else
        {
            sql = "UPDATE hst_conversations SET title=@t, updatedAt=@n WHERE conversation_id=@c";
            using var cmd = new SqlCommand(sql, (SqlConnection)conn);
            cmd.Parameters.AddWithValue("@t", title);
            cmd.Parameters.AddWithValue("@n", DateTime.UtcNow.ToString("o"));
            cmd.Parameters.AddWithValue("@c", conversationId);
            cmd.ExecuteNonQuery();
        }
    }

    public async Task AddMessageAsync(string userId, string conversationId, ChatMessage message, CancellationToken ct)
    {
        var now = DateTime.UtcNow.ToString("o");
        using var conn = await CreateConnectionAsync();
        string sql;
        
        // Get citations as JSON string for storage (matches Python behavior)
        var citationsJson = message.GetCitationsAsJsonString();
        
        // Get content as JSON string for storage - this preserves chart data structure
        var contentJson = message.GetContentAsJsonString();
        
        if (!string.IsNullOrEmpty(userId))
        {
            sql = @"INSERT INTO hst_conversation_messages (userId, conversation_id, role, content_id, content, citations, feedback, createdAt, updatedAt) 
    VALUES (@u, @c, @r, @cid, @content, @citations, @feedback, @now, @now); UPDATE hst_conversations SET updatedAt=@now WHERE conversation_id=@c;";
            using (var cmd = new SqlCommand(sql, (SqlConnection)conn))
            {
                cmd.Parameters.AddWithValue("@u", userId);
                cmd.Parameters.AddWithValue("@c", conversationId);
                cmd.Parameters.AddWithValue("@r", message.Role);
                cmd.Parameters.AddWithValue("@cid", message.Id);
                cmd.Parameters.AddWithValue("@content", contentJson);
                cmd.Parameters.AddWithValue("@citations", citationsJson);
                cmd.Parameters.AddWithValue("@feedback", message.Feedback ?? string.Empty);
                cmd.Parameters.AddWithValue("@now", now);
                cmd.ExecuteNonQuery();
            }
        }
        else
        {
            sql = @"INSERT INTO hst_conversation_messages (conversation_id, role, content_id, content, citations, feedback, createdAt, updatedAt) 
    VALUES (@c, @r, @cid, @content, @citations, @feedback, @now, @now); UPDATE hst_conversations SET updatedAt=@now WHERE conversation_id=@c;";
            using (var cmd = new SqlCommand(sql, (SqlConnection)conn))
            {
                cmd.Parameters.AddWithValue("@c", conversationId);
                cmd.Parameters.AddWithValue("@r", message.Role);
                cmd.Parameters.AddWithValue("@cid", message.Id);
                cmd.Parameters.AddWithValue("@content", contentJson);
                cmd.Parameters.AddWithValue("@citations", citationsJson);
                cmd.Parameters.AddWithValue("@feedback", message.Feedback ?? string.Empty);
                cmd.Parameters.AddWithValue("@now", now);
                cmd.ExecuteNonQuery();
            }
        }
    }

    public async Task<IReadOnlyList<ConversationSummary>> ListAsync(string userId, int offset, int limit, string sortOrder, CancellationToken ct)
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
            if (filterByUser)
            {
                sql = "SELECT conversation_id, userId, title, createdAt, updatedAt FROM hst_conversations WHERE userId=@userId ORDER BY updatedAt " + order + " OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY";
            }
            else
            {
                sql = "SELECT conversation_id, userId, title, createdAt, updatedAt FROM hst_conversations ORDER BY updatedAt " + order + " OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY";
            }
            using (var cmd = new SqlCommand(sql, (SqlConnection)conn))
            {
                if (filterByUser)
                    cmd.Parameters.AddWithValue("@userId", userId);
                cmd.Parameters.AddWithValue("@offset", offset);
                cmd.Parameters.AddWithValue("@limit", limit);
                using var reader = cmd.ExecuteReader();
                while (reader.Read())
                {
                    var createdAt = reader.IsDBNull(3) ? DateTime.UtcNow : reader.GetDateTime(3);
                    var updatedAt = reader.IsDBNull(4) ? DateTime.UtcNow : reader.GetDateTime(4);
                    var title = reader.IsDBNull(2) ? "New Conversation" : reader.GetString(2);
                    
                    // Ensure title is not empty
                    if (string.IsNullOrWhiteSpace(title))
                    {
                        title = "New Conversation";
                    }
                    
                    list.Add(new ConversationSummary
                    {
                        ConversationId = reader.GetString(0),
                        UserId = reader.GetString(1),
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
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error listing conversations for user {UserId}", userId);
        }
        return list;
    }

    public async Task<IReadOnlyList<ChatMessage>> ReadAsync(string userId, string conversationId, string sortOrder, CancellationToken ct)
    {
        var order = sortOrder.Equals("asc", StringComparison.OrdinalIgnoreCase) ? "ASC" : "DESC";
        string sql;
        bool filterByUser = !string.IsNullOrEmpty(userId);
        // REDUNDANT: Detailed message reading logging
        // Console.WriteLine($"Reading messages for user '{userId}' and conversation '{conversationId}' (filterByUser={filterByUser})");
        if (string.IsNullOrEmpty(conversationId))
            return new List<ChatMessage>();
        if (filterByUser)
        {
            sql = $"SELECT role, content, citations, feedback FROM hst_conversation_messages WHERE userId=@userId AND conversation_id=@conversationId ORDER BY updatedAt {order}";
        }
        else
        {   
            // REDUNDANT: Filter logic logging
            // Console.WriteLine("No userId provided, reading messages without user filter.");
            sql = $"SELECT role, content, citations, feedback FROM hst_conversation_messages WHERE conversation_id=@conversationId ORDER BY updatedAt {order}";
        }
        var list = new List<ChatMessage>();
        using var conn = await CreateConnectionAsync();
        using (var cmd = new SqlCommand(sql, (SqlConnection)conn))
        {
            if (filterByUser)
                cmd.Parameters.AddWithValue("@userId", userId);
            cmd.Parameters.AddWithValue("@conversationId", conversationId);
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var role = reader.IsDBNull(0) ? null : reader.GetString(0);
                var contentRaw = reader.IsDBNull(1) ? null : reader.GetString(1);
                var citationsStr = reader.IsDBNull(2) ? null : reader.GetString(2);
                var feedback = reader.IsDBNull(3) ? null : reader.GetString(3);
                
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
                    catch 
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
                    catch 
                    { 
                        // If parsing fails, treat as null
                        citations = null;
                    }
                }
                
                list.Add(new ChatMessage
                {
                    Role = role,
                    Content = content,
                    Citations = citations,
                    Feedback = feedback
                });
            }
        }
        // REDUNDANT: Message count logging
        // Console.WriteLine($"Read {list.Count} messages for conversation '{conversationId}'");
        return list;
    }

    public async Task<bool?> DeleteAsync(string userId, string conversationId, CancellationToken ct)
    {
        // 1. Check if conversation exists
        const string checkSql = "SELECT userId FROM hst_conversations WHERE conversation_id=@c";
        using var conn = await CreateConnectionAsync();
        string foundUserId = null;
        using (var checkCmd = new SqlCommand(checkSql, (SqlConnection)conn))
        {
            checkCmd.Parameters.AddWithValue("@c", conversationId);
            var result = checkCmd.ExecuteScalar();
            if (result == null)
                return null; // Not found
            foundUserId = result.ToString();
        }

        // 2. If userId is provided, check permission
        if (!string.IsNullOrEmpty(userId) && foundUserId != userId)
            return false; // Permission denied

        // 3. Delete conversation and messages
        string deleteMessagesSql, deleteConversationSql;
        SqlCommand delMsgCmd, delConvCmd;
        if (!string.IsNullOrEmpty(userId))
        {
            deleteMessagesSql = "DELETE FROM hst_conversation_messages WHERE userId=@u AND conversation_id=@c";
            deleteConversationSql = "DELETE FROM hst_conversations WHERE userId=@u AND conversation_id=@c";
            delMsgCmd = new SqlCommand(deleteMessagesSql, (SqlConnection)conn);
            delConvCmd = new SqlCommand(deleteConversationSql, (SqlConnection)conn);
            delMsgCmd.Parameters.AddWithValue("@u", userId);
            delMsgCmd.Parameters.AddWithValue("@c", conversationId);
            delConvCmd.Parameters.AddWithValue("@u", userId);
            delConvCmd.Parameters.AddWithValue("@c", conversationId);
        }
        else
        {
            deleteMessagesSql = "DELETE FROM hst_conversation_messages WHERE conversation_id=@c";
            deleteConversationSql = "DELETE FROM hst_conversations WHERE conversation_id=@c";
            delMsgCmd = new SqlCommand(deleteMessagesSql, (SqlConnection)conn);
            delConvCmd = new SqlCommand(deleteConversationSql, (SqlConnection)conn);
            delMsgCmd.Parameters.AddWithValue("@c", conversationId);
            delConvCmd.Parameters.AddWithValue("@c", conversationId);
        }
        delMsgCmd.ExecuteNonQuery();
        var rows = delConvCmd.ExecuteNonQuery();
        return rows > 0;
    }

    public async Task<int?> DeleteAllAsync(string userId, CancellationToken ct)
    {
        using var conn = await CreateConnectionAsync();
        
        string deleteMessagesSql, deleteConversationsSql;
        SqlCommand delMsgCmd, delConvCmd;
        
        // If userId is provided, delete only that user's conversations
        // If userId is null/empty, allow global delete (all conversations)
        if (!string.IsNullOrEmpty(userId))
        {
            deleteMessagesSql = "DELETE FROM hst_conversation_messages WHERE userId=@u";
            deleteConversationsSql = "DELETE FROM hst_conversations WHERE userId=@u";
            delMsgCmd = new SqlCommand(deleteMessagesSql, (SqlConnection)conn);
            delConvCmd = new SqlCommand(deleteConversationsSql, (SqlConnection)conn);
            delMsgCmd.Parameters.AddWithValue("@u", userId);
            delConvCmd.Parameters.AddWithValue("@u", userId);
        }
        else
        {
            deleteMessagesSql = "DELETE FROM hst_conversation_messages";
            deleteConversationsSql = "DELETE FROM hst_conversations";
            delMsgCmd = new SqlCommand(deleteMessagesSql, (SqlConnection)conn);
            delConvCmd = new SqlCommand(deleteConversationsSql, (SqlConnection)conn);
        }
        
        // Delete messages first, then conversations
        var messagesDeleted = delMsgCmd.ExecuteNonQuery();
        var conversationsDeleted = delConvCmd.ExecuteNonQuery();
        
        return conversationsDeleted;
    }

    public async Task<bool?> RenameAsync(string userId, string conversationId, string title, CancellationToken ct)
    {
        // 1. Check if conversation exists
        const string checkSql = "SELECT userId FROM hst_conversations WHERE conversation_id=@c";
        using var conn = await CreateConnectionAsync();
        string foundUserId = null;
        using (var checkCmd = new SqlCommand(checkSql, (SqlConnection)conn))
        {
            checkCmd.Parameters.AddWithValue("@c", conversationId);
            var result = checkCmd.ExecuteScalar();
            if (result == null)
                return null; // Not found
            foundUserId = result.ToString();
        }

        // 2. If userId is provided, check permission
        if (!string.IsNullOrEmpty(userId) && foundUserId != userId)
            return false; // Permission denied

        // 3. Update title
        string updateSql;
        SqlCommand updateCmd;
        if (!string.IsNullOrEmpty(userId))
        {
            updateSql = "UPDATE hst_conversations SET title=@t, updatedAt=@n WHERE userId=@u AND conversation_id=@c";
            updateCmd = new SqlCommand(updateSql, (SqlConnection)conn);
            updateCmd.Parameters.AddWithValue("@t", title);
            updateCmd.Parameters.AddWithValue("@n", DateTime.UtcNow.ToString("o"));
            updateCmd.Parameters.AddWithValue("@u", userId);
            updateCmd.Parameters.AddWithValue("@c", conversationId);
        }
        else
        {
            updateSql = "UPDATE hst_conversations SET title=@t, updatedAt=@n WHERE conversation_id=@c";
            updateCmd = new SqlCommand(updateSql, (SqlConnection)conn);
            updateCmd.Parameters.AddWithValue("@t", title);
            updateCmd.Parameters.AddWithValue("@n", DateTime.UtcNow.ToString("o"));
            updateCmd.Parameters.AddWithValue("@c", conversationId);
        }
        var rows = updateCmd.ExecuteNonQuery();
        return rows > 0;
    }

    public async Task<string> ExecuteChatQuery(string query, CancellationToken ct)
    {
        var results = new List<Dictionary<string, object>>();
        try
        {
            using var conn = await CreateConnectionAsync();
            using var cmd = new SqlCommand(query, (SqlConnection)conn);
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                var row = new Dictionary<string, object>();
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
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error executing chat query");
        }
        return JsonSerializer.Serialize(results);
    }

    /// <summary>
    /// Converts ODBC connection string format to SQL Server connection string format
    /// </summary>
    private string ConvertOdbcToSqlConnectionString(string odbcConnectionString)
    {
        if (string.IsNullOrWhiteSpace(odbcConnectionString))
            throw new ArgumentException("Connection string cannot be null or empty", nameof(odbcConnectionString));

        // Parse ODBC connection string
        var parts = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var pairs = odbcConnectionString.Split(';', StringSplitOptions.RemoveEmptyEntries);
        
        foreach (var pair in pairs)
        {
            var keyValue = pair.Split('=', 2, StringSplitOptions.RemoveEmptyEntries);
            if (keyValue.Length == 2)
            {
                var key = keyValue[0].Trim();
                var value = keyValue[1].Trim();
                // Remove curly braces if present
                if (value.StartsWith("{") && value.EndsWith("}"))
                    value = value.Trim('{', '}');
                parts[key] = value;
            }
        }

        // Build SQL Server connection string
        var sqlConnectionString = new List<string>();

        // Map ODBC keywords to SQL Server keywords
        if (parts.TryGetValue("SERVER", out var server))
        {
            sqlConnectionString.Add($"Server=tcp:{server},1433");
        }

        if (parts.TryGetValue("DATABASE", out var database))
        {
            sqlConnectionString.Add($"Database={database}");
        }

        if (parts.TryGetValue("UID", out var uid))
        {
            sqlConnectionString.Add($"User Id={uid}");
        }

        if (parts.TryGetValue("PWD", out var pwd))
        {
            sqlConnectionString.Add($"Password={pwd}");
        }

        if (parts.TryGetValue("Authentication", out var auth))
        {
            sqlConnectionString.Add($"Authentication={auth}");
        }

        // Add standard settings for Fabric SQL
        sqlConnectionString.Add("Encrypt=True");
        sqlConnectionString.Add("TrustServerCertificate=False");
        sqlConnectionString.Add("Connection Timeout=30");

        var result = string.Join(";", sqlConnectionString);
        _logger.LogInformation("Converted ODBC connection string to SQL Server format");
        return result;
    }    
}