import React, { useState, useEffect, useRef } from 'react';
import './KnowledgeBase.css'; // Reusing some styles, or create a new css for chat
import { useChat } from '../context/ChatContext.jsx'; // Import useChat

const RedmineAgentChat = ({ redmineUrl, redmineApiKey }) => {
    const { messages, addMessage, clearMessages } = useChat(); // Use global chat context
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

    const handleSendMessage = async () => {
        if (input.trim() === '') return;

        // Ensure redmineUrl and redmineApiKey are available
        if (!redmineUrl || !redmineApiKey) {
            alert("Redmine URL or API Key is not set. Please provide them in the Dashboard/Data Management page.");
            return;
        }

        const newUserMessage = { role: 'user', content: input };
        addMessage(newUserMessage); // Use addMessage from context
        setInput('');
        setLoading(true);

        try {
            const chatHistory = messages.map(msg => ({ role: msg.role, content: msg.content }));

            const response = await fetch('/api/redmine-agent-chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Redmine-Url': redmineUrl,
                    'X-Redmine-Api-Key': redmineApiKey,
                },
                body: JSON.stringify({
                    message: input,
                    chat_history: chatHistory
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to get response from agent');
            }

            const data = await response.json();
            addMessage({ role: 'agent', content: data.response }); // Use addMessage from context
        } catch (error) {
            console.error('Error sending message to agent:', error);
            addMessage({ role: 'agent', content: `Error: ${error.message}` }); // Use addMessage from context
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !loading) {
            handleSendMessage();
        }
    };

    return (
        <div className="knowledge-base-container">
            <h1>Redmine Agent Chat</h1>
            <p>Ask questions or give commands related to Redmine projects and issues.</p>

            <div className="chat-window">
                <div className="messages-display">
                    {messages.length === 0 && <p className="no-messages">Type a message to start chatting!</p>}
                    {messages.map((msg, index) => (
                        <div key={index} className={`message ${msg.role}`}>
                            <strong>{msg.role === 'user' ? 'You' : 'Agent'}:</strong> {msg.content}
                        </div>
                    ))}
                    {loading && <div className="message agent"><strong>Agent:</strong> Thinking...</div>}
                    <div ref={messagesEndRef} />
                </div>
                <div className="message-input-area">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Type your message..."
                        disabled={loading}
                    />
                    <button onClick={handleSendMessage} disabled={loading}>
                        {loading ? 'Sending...' : 'Send'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RedmineAgentChat;
