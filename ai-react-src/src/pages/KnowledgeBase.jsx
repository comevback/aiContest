import React, { useState, useEffect, useRef } from 'react';
import { uploadRAGFiles, getIndexingProgress, reloadRAG, askRAG, getDocuments, deleteDocument } from '../utils/api';
import ReactMarkdown from 'react-markdown';
import { ClipLoader } from 'react-spinners';
import './KnowledgeBase.css';

const KnowledgeBase = () => {
  // State for document management
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);

  // State for file upload and indexing
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [indexingTask, setIndexingTask] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [error, setError] = useState('');

  // State for chat
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const messagesEndRef = useRef(null);

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

  // Fetch documents on initial load
  useEffect(() => {
    fetchDocuments();
  }, []);

  // Polling for indexing progress
  useEffect(() => {
    if (!indexingTask || indexingTask.status === 'completed' || indexingTask.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      const result = await getIndexingProgress(indexingTask.id);
      if (result.error) {
        setError(`進捗の取得に失敗しました: ${result.error}`);
        setIndexingTask(prev => ({ ...prev, status: 'failed' }));
      } else {
        setProgress(result.progress || 0);
        setProgressMessage(result.message || '');
        if (result.status === 'completed' || result.status === 'failed') {
          setIndexingTask(prev => ({ ...prev, status: result.status }));
          if (result.status === 'completed') {
            setProgressMessage('インデックス作成完了。ナレッジベースをリロード中...');
            const reloadResult = await reloadRAG();
            if (reloadResult.error) {
                setError(`ナレッジベースのリロードに失敗しました: ${reloadResult.error}`);
                setProgressMessage('インデックス作成完了。リロードに失敗しました。');
            } else {
                setProgressMessage('ナレッジベースのリロードが完了しました！');
            }
            // Refresh document list after indexing
            fetchDocuments();
          }
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [indexingTask]);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const handleFileChange = (e) => {
    setFiles([...e.target.files]);
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('アップロードするファイルを選択してください。');
      return;
    }
    setUploading(true);
    setError('');
    setProgress(0);
    setProgressMessage('ファイルをアップロード中...');
    const result = await uploadRAGFiles(files);
    setUploading(false);
    setFiles([]); // Clear file input after upload
    if (result.error) {
      setError(result.error);
    } else {
      setIndexingTask({ id: result.task_id, status: 'pending' });
      setProgressMessage('アップロード完了。インデックス作成を開始します...');
    }
  };
  
  const handleDelete = async (filename) => {
    if (window.confirm(`本当にファイル "${filename}" を削除しますか？\nこの操作により、ナレッジベース全体の再インデックスが実行されます。`)) {
      setError('');
      setProgress(0);
      setProgressMessage(`ファイル "${filename}" を削除中...`);
      const result = await deleteDocument(filename);
      if (result.error) {
        setError(result.error);
      } else {
        setIndexingTask({ id: result.task_id, status: 'pending' });
        setProgressMessage('ファイル削除完了。再インデックスを開始します...');
      }
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const newMessages = [...messages, { sender: 'user', text: chatInput }];
    setMessages(newMessages);
    const question = chatInput;
    setChatInput('');
    setChatLoading(true);

    const result = await askRAG(question);
    setChatLoading(false);

    if (result.error) {
      setMessages([...newMessages, { sender: 'bot', text: `エラー: ${result.error}`, sources: [] }]);
    } else {
      setMessages([...newMessages, { sender: 'bot', text: result.answer, sources: result.sources }]);
    }
  };

  return (
    <div className="knowledge-base-page">
      <aside className="kb-sidebar">
        <h3>ナレッジベース文書</h3>
        {loadingDocs ? (
          <ClipLoader size={25} color={"#007bff"} />
        ) : (
          <ul className="document-list">
            {documents.length === 0 && <p style={{fontSize: '14px', color: '#666'}}>文書がありません。</p>}
            {documents.map((doc) => (
              <li key={doc} className="document-list-item">
                <span>{doc}</span>
                <button onClick={() => handleDelete(doc)} title={`Delete ${doc}`}>
                  🗑️
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <main className="kb-main-content">
        <div className="card">
          <h3>1. 文書をアップロード</h3>
          <p>PDF、TXT、Markdown、Word、Excel ファイルをアップロードして、ナレッジベースを構築・更新します。</p>
          <div className="file-input-container">
            <input type="file" multiple onChange={handleFileChange} accept=".pdf,.txt,.md,.docx,.xlsx,.xls" className="file-input" />
            <button onClick={handleUpload} disabled={uploading || (indexingTask && indexingTask.status === 'processing')}>
              {uploading ? 'アップロード中...' : 'アップロードとインデックス作成'}
            </button>
          </div>
        </div>
       
        {(uploading || indexingTask) && (
            <div className="progress-section card">
                <h3>2. インデックス作成状況</h3>
                <div className="progress-bar-container">
                    <div 
                        className={`progress-bar ${indexingTask?.status}`}
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
          <h3>3. ナレッジベースと対話</h3>
          <div className="chat-window">
            <div className="messages-container">
              {messages.map((msg, index) => (
                <div key={index} className={`chat-message ${msg.sender}`}>
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                  {msg.sender === 'bot' && msg.sources && msg.sources.length > 0 && (
                     <div className="sources-container">
                       <strong>参照元:</strong>
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
                placeholder="文書について質問を入力..."
                disabled={chatLoading}
              />
              <button onClick={handleSendMessage} disabled={chatLoading}>
                送信
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default KnowledgeBase;
