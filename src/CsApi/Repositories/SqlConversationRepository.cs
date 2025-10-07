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
    Task<string> EnsureConversationAsync(string userId, string? conversationId, string title, CancellationToken ct);
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
            var cs = _config["FABRIC_SQL_CONNECTION_STRING"];
            var sqlConn = new SqlConnection(cs);
            await sqlConn.OpenAsync();
            Console.WriteLine("✅ Connected to Fabric SQL using connection string.");
            return sqlConn;
        }

        // In dev, use Azure AD authentication (no username/password required)
        var db = _config["FABRIC_SQL_DATABASE"]?.Trim(' ', '{', '}');
        var server = _config["FABRIC_SQL_SERVER"];

        Console.WriteLine($"Using Azure CLI/Azure AD authentication for {server}, database {db}");

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
        Console.WriteLine("✅ Connected to Fabric SQL using Azure Identity (no username/password).");

        return sqlConnWithToken;

    }


    public async Task<string> EnsureConversationAsync(string userId, string? conversationId, string title, CancellationToken ct)
    {
        var id = conversationId ?? Guid.NewGuid().ToString();
        using var conn = await CreateConnectionAsync();
        
        // Check if conversation exists
        const string existsSql = "SELECT userId FROM hst_conversations WHERE conversation_id=@c";
        string foundUserId = null;
        using (var check = new SqlCommand(existsSql, (SqlConnection)conn))
        {
            check.Parameters.Add(new SqlParameter("@c", id));
            var result = check.ExecuteScalar();
            if (result != null)
            {
                foundUserId = result.ToString();
                // If conversation exists, check permission
                if (!string.IsNullOrEmpty(userId) && foundUserId != userId)
                {
                    throw new UnauthorizedAccessException($"User {userId} does not have permission to access conversation {id}");
                }
                return id; // Conversation exists and user has permission
            }
        }
        
        // Conversation doesn't exist, create it
        const string insertSql = "INSERT INTO hst_conversations (userId, conversation_id, title, createdAt, updatedAt) VALUES (@u, @c, @t, @n, @n)";
        var now = DateTime.UtcNow.ToString("o");
        using (var cmd = new SqlCommand(insertSql, (SqlConnection)conn))
        {
            cmd.Parameters.Add(new SqlParameter("@u", userId ?? string.Empty));
            cmd.Parameters.Add(new SqlParameter("@c", id));
            cmd.Parameters.Add(new SqlParameter("@t", title ?? string.Empty));
            cmd.Parameters.Add(new SqlParameter("@n", now));
            cmd.ExecuteNonQuery();
        }
        return id;
    }

    public async Task AddMessageAsync(string userId, string conversationId, ChatMessage message, CancellationToken ct)
    {
    var now = DateTime.UtcNow.ToString("o");
    using var conn = await CreateConnectionAsync();
    string sql;
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
            cmd.Parameters.AddWithValue("@content", message.Content ?? string.Empty);
            cmd.Parameters.AddWithValue("@citations", JsonSerializer.Serialize(message.Citations ?? new List<string>()));
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
            cmd.Parameters.AddWithValue("@content", message.Content ?? string.Empty);
            cmd.Parameters.AddWithValue("@citations", JsonSerializer.Serialize(message.Citations ?? new List<string>()));
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
            Console.WriteLine($"Listing conversations for user '{userId}' (filterByUser={filterByUser})");
            if (filterByUser)
            {
                sql = "SELECT conversation_id, userId, title FROM hst_conversations WHERE userId=@userId ORDER BY updatedAt " + order + " OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY";
            }
            else
            {
                sql = "SELECT conversation_id, userId, title FROM hst_conversations ORDER BY updatedAt " + order + " OFFSET @offset ROWS FETCH NEXT @limit ROWS ONLY";
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
                    list.Add(new ConversationSummary
                    {
                        ConversationId = reader.GetString(0),
                        UserId = reader.GetString(1),
                        Title = reader.GetString(2)
                    });
                }
            }
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
        Console.WriteLine($"Reading messages for user '{userId}' and conversation '{conversationId}' (filterByUser={filterByUser})");
        if (string.IsNullOrEmpty(conversationId))
            return new List<ChatMessage>();
        if (filterByUser)
        {
            sql = $"SELECT role, content, citations, feedback FROM hst_conversation_messages WHERE userId=@userId AND conversation_id=@conversationId ORDER BY updatedAt {order}";
        }
        else
        {   
            Console.WriteLine("No userId provided, reading messages without user filter.");
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
                List<string> citationsList = new();
                if (!string.IsNullOrWhiteSpace(citationsStr))
                {
                    try { citationsList = JsonSerializer.Deserialize<List<string>>(citationsStr) ?? new(); } catch { citationsList = new(); }
                }
                list.Add(new ChatMessage
                {
                    Role = role,
                    Content = contentRaw ?? string.Empty,
                    Citations = citationsList,
                    Feedback = feedback
                });
            }
        }
        Console.WriteLine($"Read {list.Count} messages for conversation '{conversationId}'");
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
                    row[colName] = value;
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
}