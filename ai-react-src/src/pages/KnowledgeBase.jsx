import React, { useState, useEffect, useRef } from 'react';
import { uploadRAGFiles, getIndexingProgress, reloadRAG, askRAG } from '../utils/api';
import ReactMarkdown from 'react-markdown';
import { ClipLoader } from 'react-spinners';
import './KnowledgeBase.css';

const KnowledgeBase = () => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [indexingTask, setIndexingTask] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [error, setError] = useState('');

  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!indexingTask || indexingTask.status === 'completed' || indexingTask.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      const result = await getIndexingProgress(indexingTask.id);
      if (result.error) {
        setError(`Failed to get progress: ${result.error}`);
        setIndexingTask(prev => ({ ...prev, status: 'failed' }));
      } else {
        setProgress(result.progress || 0);
        setProgressMessage(result.message || '');
        if (result.status === 'completed' || result.status === 'failed') {
          setIndexingTask(prev => ({ ...prev, status: result.status }));
          if (result.status === 'completed') {
            // Automatically reload the RAG service
            setProgressMessage('Indexing complete. Reloading knowledge base...');
            const reloadResult = await reloadRAG();
            if (reloadResult.error) {
                setError(`Failed to reload knowledge base: ${reloadResult.error}`);
                setProgressMessage('Indexing complete, but failed to auto-reload knowledge base.');
            } else {
                setProgressMessage('Knowledge base reloaded successfully! Ready to chat.');
            }
          }
        }
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [indexingTask]);

  const handleFileChange = (e) => {
    setFiles([...e.target.files]);
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select files to upload.');
      return;
    }

    setUploading(true);
    setError('');
    setProgress(0);
    setProgressMessage('Uploading files...');

    const result = await uploadRAGFiles(files);

    setUploading(false);

    if (result.error) {
      setError(result.error);
    } else {
      setIndexingTask({ id: result.task_id, status: 'pending' });
      setProgressMessage('Upload complete. Starting indexing...');
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const newMessages = [...messages, { sender: 'user', text: chatInput }];
    setMessages(newMessages);
    setChatInput('');
    setChatLoading(true);

    const result = await askRAG(chatInput);

    setChatLoading(false);

    if (result.error) {
      setMessages([...newMessages, { sender: 'bot', text: `Error: ${result.error}`, sources: [] }]);
    } else {
      setMessages([...newMessages, { sender: 'bot', text: result.answer, sources: result.sources }]);
    }
  };

  return (
    <div className="knowledge-base-page">
      <div className="kb-container">
        <h2>Knowledge Base Management</h2>
        <p>Upload PDF documents to build or update the knowledge base for the RAG agent.</p>

        <div className="upload-section card">
          <h3>1. Upload Documents</h3>
          <div className="file-input-container">
            <input type="file" multiple onChange={handleFileChange} accept=".pdf,.txt,.md,.docx,.xlsx,.xls" className="file-input" />
            <button onClick={handleUpload} disabled={uploading || (indexingTask && indexingTask.status === 'processing')}>
              {uploading ? 'Uploading...' : 'Upload and Index'}
            </button>
          </div>
           {files.length > 0 && (
            <ul className="file-list">
              {Array.from(files).map((file, index) => (
                <li key={index}>{file.name}</li>
              ))}
            </ul>
          )}
        </div>
       
        {indexingTask && (
            <div className="progress-section card">
                <h3>2. Indexing Progress</h3>
                <div className="progress-bar-container">
                    <div 
                        className={`progress-bar ${indexingTask.status}`}
                        style={{ width: `${progress}%` }}
                    >
                        {progress}%
                    </div>
                </div>
                <p className="progress-message">{progressMessage}</p>
                 {error && <p className="error-message">{error}</p>}
            </div>
        )}

        <div className="chat-section card">
          <h3>3. Chat with your Knowledge Base</h3>
          <div className="chat-window">
            <div className="messages-container">
              {messages.map((msg, index) => (
                <div key={index} className={`chat-message ${msg.sender}`}>
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                  {msg.sender === 'bot' && msg.sources && msg.sources.length > 0 && (
                     <div className="sources-container">
                       <strong>Sources:</strong>
                       <ul>
                         {msg.sources.map((source, i) => (
                           <li key={i} title={source.page_content}>
                             {source.source}
                           </li>
                         ))}
                       </ul>
                     </div>
                  )}
                </div>
              ))}
               {chatLoading && (
                <div className="chat-message bot">
                  <ClipLoader size={20} color={"#333"} />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <div className="chat-input-container">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Ask a question about the documents..."
                disabled={chatLoading}
              />
              <button onClick={handleSendMessage} disabled={chatLoading}>
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBase;
