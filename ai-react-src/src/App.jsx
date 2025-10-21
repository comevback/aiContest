import React, { useState, useEffect } from 'react';
import './App.css';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import IssueAnalysis from './pages/IssueAnalysis';
import ProgressPrediction from './pages/ProgressPrediction';
import DataManagement from './pages/DataManagement';
import { getProjects, setRedmineCredentials } from './utils/api'; // Will add setRedmineCredentials
import { ClipLoader } from 'react-spinners';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [redmineUrl, setRedmineUrl] = useState(localStorage.getItem('redmineUrl') || '');
  const [redmineApiKey, setRedmineApiKey] = useState(localStorage.getItem('redmineApiKey') || '');
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [projectsError, setProjectsError] = useState(null);
  const [credentialsSet, setCredentialsSet] = useState(!!(redmineUrl && redmineApiKey));

  useEffect(() => {
    if (credentialsSet) {
      setRedmineCredentials(redmineUrl, redmineApiKey); // Set credentials in api.js
      fetchAllProjects();
    }
  }, [credentialsSet, redmineUrl, redmineApiKey]); // Depend on credentialsSet and credentials themselves

  const fetchAllProjects = async () => {
    setLoadingProjects(true);
    setProjectsError(null);
    try {
      const data = await getProjects();
      if (data.error) {
        setProjectsError(data.error);
        setProjects([]);
        setCredentialsSet(false); // If credentials fail, reset
      } else if (data.projects) {
        setProjects(data.projects);
        if (data.projects.length > 0) {
          setSelectedProject(data.projects[0].id);
        }
      }
    } catch (err) {
      setProjectsError('プロジェクトの取得に失敗しました');
      console.error(err);
      setCredentialsSet(false); // If credentials fail, reset
    } finally {
      setLoadingProjects(false);
    }
  };

  const handleConnect = () => {
    if (redmineUrl && redmineApiKey) {
      localStorage.setItem('redmineUrl', redmineUrl);
      localStorage.setItem('redmineApiKey', redmineApiKey);
      setCredentialsSet(true);
    } else {
      setProjectsError('Redmine URLとAPIキーを入力してください。');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('redmineUrl');
    localStorage.removeItem('redmineApiKey');
    setRedmineUrl('');
    setRedmineApiKey('');
    setCredentialsSet(false);
    setProjects([]); // Clear projects
    setSelectedProject(null); // Clear selected project
    setProjectsError(null); // Clear any previous errors
    setCurrentPage('dashboard'); // Go back to dashboard
  };

  const renderPage = () => {
    const commonProps = {
      projects,
      selectedProject,
      setSelectedProject,
      loadingProjects,
      projectsError,
      redmineUrl, // Pass credentials down
      redmineApiKey, // Pass credentials down
    };

    switch (currentPage) {
      case 'dashboard':
        return <Dashboard {...commonProps} />;
      case 'issue-analysis':
        return <IssueAnalysis {...commonProps} />;
      case 'progress-prediction':
        return <ProgressPrediction {...commonProps} />;
      case 'data-management':
        return <DataManagement {...commonProps} />;
      default:
        return <Dashboard {...commonProps} />;
    }
  };

  return (
    <div className="app">
      <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} onLogout={handleLogout} />
      <main className="main-content">
        {!credentialsSet ? (
          <div style={{ padding: '20px', maxWidth: '500px', margin: '50px auto', backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
            <h2 style={{ marginBottom: '20px', textAlign: 'center' }}>Redmine 接続設定</h2>
            {projectsError && <div className="error" style={{ marginBottom: '15px', textAlign: 'center' }}>{projectsError}</div>}
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Redmine URL:</label>
              <input
                type="text"
                value={redmineUrl}
                onChange={(e) => setRedmineUrl(e.target.value)}
                placeholder="例: http://your-redmine.com"
                style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}
              />
            </div>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Redmine API キー:</label>
              <input
                type="text"
                value={redmineApiKey}
                onChange={(e) => setRedmineApiKey(e.target.value)}
                placeholder="APIキーを入力"
                style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ddd' }}
              />
            </div>
            <button
              onClick={handleConnect}
              disabled={loadingProjects}
              style={{
                width: '100%',
                padding: '12px',
                backgroundColor: '#4A90E2',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: loadingProjects ? 'not-allowed' : 'pointer',
                fontSize: '16px',
                fontWeight: '600',
                transition: 'background-color 0.3s ease',
                opacity: loadingProjects ? 0.6 : 1,
              }}
            >
              {loadingProjects ? <ClipLoader color="white" size={20} /> : '接続してプロジェクトを読み込む'}
            </button>
          </div>
        ) : (
          loadingProjects ? (
            <div className="loading-container">
              <ClipLoader color="#4A90E2" size={50} />
              <p>プロジェクトを読み込み中...</p>
            </div>
          ) : projectsError ? (
            <div className="error">{projectsError}</div>
          ) : (
            renderPage()
          )
        )}
      </main>
    </div>
  );
}

export default App;
