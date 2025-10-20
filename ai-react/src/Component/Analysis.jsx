import React, { useState, useEffect } from 'react';
import { getProjects, analyzeProject } from '../Service/api';
import ReactMarkdown from 'react-markdown';
import ClipLoader from "react-spinners/ClipLoader";

const Analysis = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(false);

  useEffect(() => {
    const fetchProjects = async () => {
      setLoadingProjects(true);
      setError(null);
      try {
        const result = await getProjects();
        if (result.error) {
          setError(result.error);
        } else {
          setProjects(result.projects || []);
        }
      } catch (err) {
        setError(err.message || 'Failed to get projects.');
      }
      setLoadingProjects(false);
    };

    fetchProjects();
  }, []);

  const handleAnalyze = async (project) => {
    if (selectedProject?.id === project.id && analysis) return;

    setSelectedProject(project);
    setLoading(true);
    setError(null);
    setAnalysis(null);

    try {
      const result = await analyzeProject(project.identifier);
      if (result.error) {
        setError(result.error);
      } else {
        setAnalysis(result.analysis);
      }
    } catch (err) {
      setError(err.message || 'Failed to get analysis.');
    }
    setLoading(false);
  };

  return (
    <div className="analysis-container">
      <aside className="sidebar">
        <h2>Projects</h2>
        {loadingProjects ? (
          <p>Loading projects...</p>
        ) : (
          <div className="project-list">
            {projects.map((project) => (
              <button
                key={project.id}
                onClick={() => handleAnalyze(project)}
                disabled={loading}
                className={selectedProject?.id === project.id ? 'selected' : ''}
              >
                {project.name}
              </button>
            ))}
          </div>
        )}
      </aside>
      <main className="main-content">
        {error && <div className="error-message">Error: {error}</div>}
        {loading ? (
          <div className="loading-indicator">
            <ClipLoader color={"#3498db"} loading={loading} size={50} />
            <p>Analyzing {selectedProject?.name}...</p>
          </div>
        ) : analysis && selectedProject ? (
          <div className="analysis-result">
            <h2>Analysis for {selectedProject.name}</h2>
            <ReactMarkdown>{analysis}</ReactMarkdown>
          </div>
        ) : (
          <div className="placeholder">
            <p>Select a project to begin analysis.</p>
            <p>Your project insights will appear here.</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default Analysis;