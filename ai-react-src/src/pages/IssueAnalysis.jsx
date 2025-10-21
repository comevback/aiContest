import React, { useState, useEffect } from 'react';
import { analyzeProject } from '../utils/api';

const IssueAnalysis = ({ projects, selectedProject, setSelectedProject, loadingProjects, projectsError }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const handleAnalyze = async (project) => {
    if (selectedProject === project.id && analysis) return; // Prevent re-analysis if same project and analysis exists

    setSelectedProject(project.id);
    setLoadingAnalysis(true);
    setAnalysisError(null);
    setAnalysis(null);

    try {
      const result = await analyzeProject(project.identifier || project.id);
      if (result.error) {
        setAnalysisError(result.error);
      } else {
        setAnalysis(result.analysis);
      }
    } catch (err) {
      setAnalysisError(err.message || '分析に失敗しました');
    }
    setLoadingAnalysis(false);
  };

  if (loadingProjects) {
    return <div className="loading">プロジェクトを読み込み中...</div>;
  }

  if (projectsError) {
    return <div className="error">{projectsError}</div>;
  }

  return (
    <div className="dashboard-container">
      <h1 className="page-title">課題分析</h1>
      <p className="page-subtitle">AI による Redmine 工単の詳細分析</p>

      {analysisError && <div className="error">{analysisError}</div>}

      <div className="project-selector">
        <label style={{ marginRight: '10px', fontWeight: '500', display: 'block', marginBottom: '10px' }}>
          プロジェクト選択:
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))' , gap: '10px' }}>
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => handleAnalyze(project)}
              disabled={loadingAnalysis}
              style={{
                padding: '15px',
                borderRadius: '6px',
                border: selectedProject === project.id ? '2px solid #50c878' : '1px solid #ddd',
                backgroundColor: selectedProject === project.id ? '#f0f9f6' : '#fff',
                cursor: loadingAnalysis ? 'not-allowed' : 'pointer',
                fontSize: '14px',
                fontWeight: selectedProject === project.id ? '600' : '500',
                color: selectedProject === project.id ? '#50c878' : '#333',
                transition: 'all 0.3s ease',
                textAlign: 'left',
                opacity: loadingAnalysis ? 0.6 : 1,
              }}
              onMouseEnter={(e) => {
                if (!loadingAnalysis && selectedProject !== project.id) {
                  e.target.style.backgroundColor = '#f5f5f5';
                }
              }}
              onMouseLeave={(e) => {
                if (!loadingAnalysis && selectedProject !== project.id) {
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

      {loadingAnalysis && (
        <div className="loading">
          分析中...
        </div>
      )}

      {analysis && !loadingAnalysis && (
        <div className="analysis-result">
          <h2>分析結果</h2>
          <div className="analysis-result-content">
            {analysis}
          </div>
        </div>
      )}

      {!analysis && !loadingAnalysis && selectedProject && (
        <div className="empty-state">
          プロジェクトを選択して分析を実行してください
        </div>
      )}

      {projects.length === 0 && !loadingAnalysis && (
        <div className="empty-state">
          利用可能なプロジェクトがありません
        </div>
      )}
    </div>
  );
};

export default IssueAnalysis;