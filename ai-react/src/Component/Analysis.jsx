import React, { useState, useEffect } from 'react';
import { getProjects, analyzeProject } from '../Service/api';
import ReactMarkdown from 'react-markdown';

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
    <div>
      <h1>Redmine Project Analysis</h1>

      {loadingProjects && <p>Loading projects...</p>}

      {error && <div style={{ color: 'red' }}>Error: {error}</div>}

      {!loadingProjects && !error && (
        <div>
          <h2>Select a Project to Analyze</h2>
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
        </div>
      )}

      {loading && selectedProject && <p>Analyzing {selectedProject.name}...</p>}

      {analysis && selectedProject && (
        <div className="analysis-result">
          <h2>Analysis for {selectedProject.name}</h2>
          <ReactMarkdown>{analysis}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

export default Analysis;