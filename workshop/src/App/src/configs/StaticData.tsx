const conversations = [
  {
    _attachments: "attachments/",
    _etag: '"1700d350-0000-0400-0000-673aeadc0000"',
    _rid: "L4pzAPJpN2I3AAAAAAAAAA==",
    _self: "dbs/L4pzAA==/colls/L4pzAPJpN2I=/docs/L4pzAPJpN2I3AAAAAAAAAA==/",
    _ts: 1731914460,
    conversationId: "c6430b2c-3bc6-4259-a695-db31af20e52c",
    createdAt: "2024-11-18T07:20:34.325091",
    id: "c6430b2c-3bc6-4259-a695-db31af20e52c",
    title: "Introducing the conversation",
    type: "conversation",
    updatedAt: "2024-11-18T07:21:00.469430",
    userId: "4b16c510-aecd-4016-9581-5467bfe2b8f3",
  },
  {
    _attachments: "attachments/",
    _etag: '"17003950-0000-0400-0000-673aeacf0000"',
    _rid: "L4pzAPJpN2I7AAAAAAAAAA==",
    _self: "dbs/L4pzAA==/colls/L4pzAPJpN2I=/docs/L4pzAPJpN2I7AAAAAAAAAA==/",
    _ts: 1731914447,
    conversationId: "128cbe0a-cc7e-4cd6-a217-cfe2547cf1e7",
    createdAt: "2024-11-18T07:20:47.577407",
    id: "128cbe0a-cc7e-4cd6-a217-cfe2547cf1e7",
    title: "Greeting exchange initiation",
    type: "conversation",
    updatedAt: "2024-11-18T07:20:47.707249",
    userId: "4b16c510-aecd-4016-9581-5467bfe2b8f3",
  },
];

export const historyListResponse = [].concat(...Array(0).fill(conversations));
export const historyReadResponse = {
  "conversation_id": "c6430b2c-3bc6-4259-a695-db31af20e52c",
  "messages": [
      {
          "content": "hi",
          "createdAt": "2024-11-27T08:00:38.706Z",
          "feedback": null,
          "id": "301cc2d1-aba6-47a9-8362-f44c63d52ce3",
          "role": "user",
          "context":'',
          "contentType":''
      },
      {
          "content": "Hello! How can I assist you today?",
          "createdAt": "2024-11-27T08:00:38.867Z",
          "feedback": null,
          "id": "a2521228-0f88-401f-9d39-d78e0a3ef2cd",
          "role": "assistant",
           "context":'',
          "contentType":''
      }
  ]
};
