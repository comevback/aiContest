import React, { useState } from 'react';
import { analyzeProject } from '../Service/api';

const Analysis = () => {
  const [projectId, setProjectId] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!projectId) {
      setError('Project ID is required.');
      return;
    }

    setLoading(true);
    setError(null);
    setAnalysis(null);

    try {
      const result = await analyzeProject(projectId);
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
      <form onSubmit={handleAnalyze}>
        <input
          type="text"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          placeholder="Enter Redmine Project ID"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>

      {error && <div style={{ color: 'red' }}>Error: {error}</div>}

      {analysis && (
        <div>
          <h2>Analysis Result</h2>
          <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
            {analysis}
          </pre>
        </div>
      )}
    </div>
  );
};

export default Analysis;