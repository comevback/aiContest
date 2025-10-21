import React, { useState, useEffect } from 'react';
import './App.css';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import IssueAnalysis from './pages/IssueAnalysis';
import ProgressPrediction from './pages/ProgressPrediction';
import DataManagement from './pages/DataManagement';
import { getProjects } from './utils/api';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [projectsError, setProjectsError] = useState(null);

  useEffect(() => {
    const fetchAllProjects = async () => {
      setLoadingProjects(true);
      try {
        const data = await getProjects();
        if (data.error) {
          setProjectsError(data.error);
        } else if (data.projects) {
          setProjects(data.projects);
          if (data.projects.length > 0) {
            setSelectedProject(data.projects[0].id);
          }
        }
      } catch (err) {
        setProjectsError('プロジェクトの取得に失敗しました');
        console.error(err);
      } finally {
        setLoadingProjects(false);
      }
    };
    fetchAllProjects();
  }, []);

  const renderPage = () => {
    const commonProps = {
      projects,
      selectedProject,
      setSelectedProject,
      loadingProjects,
      projectsError,
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
      <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <main className="main-content">
        {loadingProjects ? (
          <div className="loading">プロジェクトを読み込み中...</div>
        ) : projectsError ? (
          <div className="error">{projectsError}</div>
        ) : (
          renderPage()
        )}
      </main>
    </div>
  );
}

export default App;