import React, { useState, useEffect, useRef } from 'react';
import { uploadRAGFiles, getIndexingProgress, reloadRAG, askRAG, getDocuments, deleteDocument } from '../utils/api';
import ReactMarkdown from 'react-markdown';
import { ClipLoader } from 'react-spinners';
import './KnowledgeBase.css';
import { useChat } from '../context/ChatContext.jsx'; // Import useChat

const KnowledgeBase = () => {
  // Document Management State
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);

  // Upload & Indexing State
  const [files, setFiles] = useState([]);
  const [indexingTask, setIndexingTask] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [error, setError] = useState('');
  
  // Chat State - now using global context
  const { messages, addMessage } = useChat();
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Refs
  const inputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // --- Effects ---
  const fetchDocuments = async () => {
    setLoadingDocs(true);
    const result = await getDocuments();
    if (result.error) {
      setError(`文書一覧の取得に失敗しました: ${result.error}`);
    } else {
      setDocuments(result.documents || []);
    }
    setLoadingDocs(false);
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    if (!indexingTask) return;

    if (indexingTask.status === 'completed') {
        const timer = setTimeout(() => {
            setIndexingTask(null);
            setProgressMessage('');
        }, 3000); // Hide after 3 seconds on success
        return () => clearTimeout(timer);
    }
    if (indexingTask.status === 'failed') {
        return; // Persist on failure until dismissed
    }

    const interval = setInterval(async () => {
      const result = await getIndexingProgress(indexingTask.id);
      if (result.error) {
        setIndexingTask(prev => ({ ...prev, status: 'failed', message: `進捗の取得に失敗しました: ${result.error}` }));
      } else {
        setProgress(result.progress || 0);
        setProgressMessage(result.message || '');
        if (result.status === 'completed' || result.status === 'failed') {
          if (result.status === 'completed') {
            setProgressMessage('インデックス作成完了。ナレッジベースをリロード中...');
            const reloadResult = await reloadRAG();
            if (reloadResult.error) {
                setIndexingTask(prev => ({ ...prev, status: 'failed', message: `リロード失敗: ${reloadResult.error}` }));
            } else {
                setIndexingTask(prev => ({ ...prev, status: 'completed', message: 'ナレッジベースのリロードが完了しました！' }));
            }
          } else {
             setIndexingTask(prev => ({ ...prev, status: 'failed', message: result.message }));
          }
          fetchDocuments();
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [indexingTask]);
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- Event Handlers ---
  const handleFileSelect = (e) => {
    e.preventDefault();
    if (e.target.files?.[0]) {
      setFiles(Array.from(e.target.files));
    }
    e.target.value = null; // Allow re-selecting the same file
  };

  const onSelectButtonClick = () => {
    inputRef.current?.click();
  };

  const handleImport = async () => {
    if (files.length === 0) return;
    setError('');
    setIndexingTask({ status: 'processing', progress: 0, message: 'ファイルをアップロード中...' });
    const result = await uploadRAGFiles(files);
    setFiles([]);
    if (result.error) {
      setIndexingTask({ status: 'failed', message: result.error });
    } else {
      setIndexingTask(prev => ({ ...prev, id: result.task_id, message: 'アップロード完了。インデックス作成を開始します...' }));
    }
  };
  
  const handleDelete = async (filename) => {
    if (window.confirm(`本当にファイル "${filename}" を削除しますか？\nこの操作により、ナレッジベース全体の再インデックスが実行されます。`)) {
      setError('');
      setIndexingTask({ status: 'processing', progress: 0, message: `ファイル "${filename}" を削除中...` });
      const result = await deleteDocument(filename);
      if (result.error) {
        setIndexingTask({ status: 'failed', message: result.error });
      } else {
        setIndexingTask(prev => ({ ...prev, id: result.task_id, message: 'ファイル削除完了。再インデックスを開始します...' }));
      }
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMessage = { sender: 'user', text: chatInput };
    addMessage(userMessage); // Use addMessage from context
    const question = chatInput;
    setChatInput('');
    setChatLoading(true);
    const result = await askRAG(question);
    setChatLoading(false);
    if (result.error) {
      addMessage({ sender: 'bot', text: `エラー: ${result.error}`, sources: [] }); // Use addMessage from context
    } else {
      addMessage({ sender: 'bot', text: result.answer, sources: result.sources }); // Use addMessage from context
    }
  };

  return (
    <div className="knowledge-base-page">
      <aside className="kb-sidebar">
        {/* Upload Widget */}
        <div className="upload-widget">
          <h4>文書管理</h4>
          <input ref={inputRef} type="file" multiple onChange={handleFileSelect} style={{display: 'none'}} accept=".pdf,.txt,.md,.docx,.xlsx,.xls"/>
          <div className="upload-actions">
            <button onClick={onSelectButtonClick} className="select-btn">
              ファイルを選択
            </button>
            <button onClick={handleImport} className="import-btn" disabled={files.length === 0 || (indexingTask && indexingTask.status === 'processing')}> 
              インポート
            </button>
          </div>
          {files.length > 0 && (
            <div className="selected-files-list">
              <strong>選択中のファイル:</strong>
              <ul>{files.map(f => <li key={f.name}>{f.name}</li>)}</ul>
            </div>
          )}
        </div>

        {/* Progress Section */}
        {indexingTask && (
          <div className="progress-section">
            <div className="progress-bar-container">
              <div className={`progress-bar ${indexingTask?.status}`} style={{ width: `${progress}%` }}>
                {progress}%
              </div>
            </div>
            <p className="progress-message">{progressMessage}</p>
            {indexingTask.status === 'failed' && (
              <button onClick={() => setIndexingTask(null)} style={{width: '100%', marginTop: '10px', fontSize: '12px', padding: '5px 10px'}}>
                閉じる
              </button>
            )}
          </div>
        )}

        {/* Document List */}
        <div className="doc-list-container">
          <h3>ナレッジベース文書</h3>
          {loadingDocs ? <ClipLoader size={25} color={"#007bff"} /> : (
            <ul className="document-list">
              {documents.length === 0 && <p style={{fontSize: '14px', color: '#666'}}>文書がありません。</p>}
              {documents.map((doc) => (
                <li key={doc} className="document-list-item">
                  <span>{doc}</span>
                  <button onClick={() => handleDelete(doc)} title={`Delete ${doc}`}>🗑️</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <main className="kb-main-content">
        <div className="chat-section">
          <div className="chat-window">
            <div className="messages-container">
               {messages.length === 0 && <div style={{textAlign: 'center', color: '#888', margin: 'auto'}}>ドキュメントをインポートして、質問を開始してください。</div>}
              {messages.map((msg, index) => (
                <div key={index} className={`chat-message ${msg.sender}`}>
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                  {msg.sender === 'bot' && msg.sources && msg.sources.length > 0 && (
                     <div className="sources-container">
                       <strong>参照元:</strong>
                       <ul>{msg.sources.map((source, i) => <li key={i} title={source.page_content}>{source.source}</li>)}</ul>
                     </div>
                  )}
                </div>
              ))}
               {chatLoading && <div className="chat-message bot"><ClipLoader size={20} color={"#333"} /></div>}
              <div ref={messagesEndRef} />
            </div>
            <div className="chat-input-container">
              <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()} placeholder="文書について質問を入力..." />
              <button onClick={handleSendMessage} disabled={chatLoading}>送信</button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default KnowledgeBase;
