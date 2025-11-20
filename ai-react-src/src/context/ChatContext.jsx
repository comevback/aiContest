import React, { createContext, useState, useContext, useEffect } from 'react';

const ChatContext = createContext();

export const ChatProvider = ({ children }) => {
  const [messages, setMessages] = useState(() => {
    // Initialize state from localStorage or an empty array
    try {
      const storedMessages = localStorage.getItem('ragChatMessages');
      return storedMessages ? JSON.parse(storedMessages) : [];
    } catch (error) {
      console.error("Failed to parse RAG chat messages from localStorage:", error);
      return [];
    }
  });

  useEffect(() => {
    // Save messages to localStorage whenever they change
    try {
      localStorage.setItem('ragChatMessages', JSON.stringify(messages));
    } catch (error) {
      console.error("Failed to save RAG chat messages to localStorage:", error);
    }
  }, [messages]);

  // Function to add a new message
  const addMessage = (message) => {
    setMessages((prevMessages) => [...prevMessages, message]);
  };

  // Function to clear all messages
  const clearMessages = () => {
    setMessages([]);
  };

  return (
    <ChatContext.Provider value={{ messages, addMessage, clearMessages }}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};
