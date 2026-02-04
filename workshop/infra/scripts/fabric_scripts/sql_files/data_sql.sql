DROP TABLE IF EXISTS [dbo].[hst_conversation_messages];
CREATE TABLE [dbo].[hst_conversation_messages](
    [Id] [int] IDENTITY(1,1) NOT NULL,
    [userId] [nvarchar](50) NULL,
    [conversation_id] [nvarchar](50) NOT NULL,
    [role] [nvarchar](50) NULL,
    [content_id] [nvarchar](50) NULL,
    [content] [nvarchar](max) NULL,
    [citations] [nvarchar](max) NULL,
    [feedback] [nvarchar](max) NULL,
    [createdAt] [datetime2](7) NOT NULL,
    [updatedAt] [datetime2](7) NOT NULL);
 
DROP TABLE IF EXISTS [dbo].[hst_conversations];
CREATE TABLE [dbo].[hst_conversations](
    [Id] [int] IDENTITY(1,1) NOT NULL,
    [userId] [nvarchar](50) NULL,
    [conversation_id] [nvarchar](50) NOT NULL,
    [title] [nvarchar](255) NULL,
    [createdAt] [datetime2](7) NOT NULL,
    [updatedAt] [datetime2](7) NOT NULL); 
