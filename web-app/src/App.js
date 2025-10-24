import React from 'react';
import { ChatProvider, ChatHeader, MessageList, MessageInput } from 'react-ag-ui';
import { HttpAgent } from '@ag-ui/client';
import 'react-ag-ui/dist/styles.css';

const agent = new HttpAgent({
  url: 'http://127.0.0.1:8000/', // your backend endpoint
  description: 'My Pydantic AI Agent',
});

function App() {
  return (
    <ChatProvider agent={agent} threadId="demo-thread">
      <div style={{ width: '100%', height: '100vh', border: '1px solid #ccc', display: 'flex', flexDirection: 'column' }}>
        <ChatHeader />
        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          <MessageList />
        </div>
        <MessageInput />
      </div>
    </ChatProvider>
  );
}

export default App;
