import React, { useState, useEffect } from 'react';
import { getProjects, analyzeProject } from '../utils/api';

const IssueAnalysis = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await getProjects();
      if (data.error) {
        setError(data.error);
      } else if (data.projects) {
        setProjects(data.projects);
        if (data.projects.length > 0) {
          setSelectedProject(data.projects[0]);
        }
      }
    } catch (err) {
      setError('プロジェクトの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (project) => {
    if (selectedProject?.id === project.id && analysis) return;

    setSelectedProject(project);
    setLoading(true);
    setError(null);
    setAnalysis(null);

    try {
      const result = await analyzeProject(project.identifier || project.id);
      if (result.error) {
        setError(result.error);
      } else {
        setAnalysis(result.analysis);
      }
    } catch (err) {
      setError(err.message || '分析に失敗しました');
    }
    setLoading(false);
  };

  return (
    <div className="dashboard-container">
      <h1 className="page-title">課題分析</h1>
      <p className="page-subtitle">AI による Redmine 工単の詳細分析</p>

      {error && <div className="error">{error}</div>}

      <div className="project-selector">
        <label style={{ marginRight: '10px', fontWeight: '500', display: 'block', marginBottom: '10px' }}>
          プロジェクト選択:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '10px' }}>
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => handleAnalyze(project)}
              disabled={loading}
              style={{
                padding: '15px',
                borderRadius: '6px',
                border: selectedProject?.id === project.id ? '2px solid #50c878' : '1px solid #ddd',
                backgroundColor: selectedProject?.id === project.id ? '#f0f9f6' : '#fff',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: selectedProject?.id === project.id ? '600' : '500',
                color: selectedProject?.id === project.id ? '#50c878' : '#333',
                transition: 'all 0.3s ease',
                textAlign: 'left',
                opacity: loading ? 0.6 : 1,
              }}
              onMouseEnter={(e) => {
                if (!loading && selectedProject?.id !== project.id) {
                  e.target.style.backgroundColor = '#f5f5f5';
                }
              }}
              onMouseLeave={(e) => {
                if (!loading && selectedProject?.id !== project.id) {
                  e.target.style.backgroundColor = '#fff';
                }
              }}
            >
              <div style={{ fontWeight: '600', marginBottom: '5px' }}>{project.name}</div>
              <div style={{ fontSize: '12px', color: '#999' }}>{project.identifier}</div>
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="loading">
          分析中...
        </div>
      )}

      {analysis && !loading && (
        <div className="analysis-result">
          <h2>分析結果</h2>
          <div className="analysis-result-content">
            {analysis}
          </div>
        </div>
      )}

      {!analysis && !loading && selectedProject && (
        <div className="empty-state">
          プロジェクトを選択して分析を実行してください
        </div>
      )}

      {projects.length === 0 && !loading && (
        <div className="empty-state">
          利用可能なプロジェクトがありません
        </div>
      )}
    </div>
  );
};

export default IssueAnalysis;

