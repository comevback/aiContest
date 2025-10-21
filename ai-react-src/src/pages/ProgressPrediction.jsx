import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getProjectProgressPrediction, getIssueProgressPrediction, getIssues } from '../utils/api';
import { ClipLoader } from 'react-spinners';

const ProgressPrediction = ({ projects, selectedProject, setSelectedProject, loadingProjects, projectsError }) => {
  const [projectPredictionData, setProjectPredictionData] = useState([]);
  const [projectPredictionSummary, setProjectPredictionSummary] = useState("");
  const [loadingProjectPrediction, setLoadingProjectPrediction] = useState(false);
  const [projectPredictionError, setProjectPredictionError] = useState(null);

  const [issues, setIssues] = useState([]);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [issuesError, setIssuesError] = useState(null);

  const [selectedIssue, setSelectedIssue] = useState(null);
  const [issuePredictionData, setIssuePredictionData] = useState([]);
  const [issuePredictionSummary, setIssuePredictionSummary] = useState("");
  const [loadingIssuePrediction, setLoadingIssuePrediction] = useState(false);
  const [issuePredictionError, setIssuePredictionError] = useState(null);

  // Fetch project-level prediction and issues when selectedProject changes
  useEffect(() => {
    if (selectedProject) {
      fetchProjectPrediction(selectedProject);
      fetchIssuesForProject(selectedProject);
    }
  }, [selectedProject]);

  // Fetch individual issue prediction when selectedIssue changes
  useEffect(() => {
    if (selectedIssue) {
      fetchIssuePrediction(selectedIssue);
    }
  }, [selectedIssue]);

  const fetchProjectPrediction = async (projectId) => {
    setLoadingProjectPrediction(true);
    setProjectPredictionError(null);
    try {
      const data = await getProjectProgressPrediction(projectId);
      if (data.error) {
        setProjectPredictionError(data.error);
        setProjectPredictionData([]);
        setProjectPredictionSummary("");
      } else if (data.progress_data) {
        setProjectPredictionData(data.progress_data);
        setProjectPredictionSummary(data.summary || "");
      } else {
        setProjectPredictionData([]);
        setProjectPredictionSummary("");
      }
    } catch (err) {
      setProjectPredictionError('プロジェクト進捗予測データの取得に失敗しました');
      console.error(err);
    } finally {
      setLoadingProjectPrediction(false);
    }
  };

  const fetchIssuesForProject = async (projectId) => {
    setLoadingIssues(true);
    setIssuesError(null);
    try {
      const data = await getIssues(projectId);
      if (data.error) {
        setIssuesError(data.error);
        setIssues([]);
      } else if (data.issues) {
        setIssues(data.issues);
      } else {
        setIssues([]);
      }
    } catch (err) {
      setIssuesError('プロジェクトの課題取得に失敗しました');
      console.error(err);
    } finally {
      setLoadingIssues(false);
    }
  };

  const fetchIssuePrediction = async (issueId) => {
    setLoadingIssuePrediction(true);
    setIssuePredictionError(null);
    try {
      const data = await getIssueProgressPrediction(issueId);
      if (data.error) {
        setIssuePredictionError(data.error);
        setIssuePredictionData([]);
        setIssuePredictionSummary("");
      } else if (data.progress_data) {
        setIssuePredictionData(data.progress_data);
        setIssuePredictionSummary(data.summary || "");
      } else {
        setIssuePredictionData([]);
        setIssuePredictionSummary("");
      }
    } catch (err) {
      setIssuePredictionError('課題進捗予測データの取得に失敗しました');
      console.error(err);
    } finally {
      setLoadingIssuePrediction(false);
    }
  };

  if (loadingProjects) {
    return (
      <div className="loading-container">
        <ClipLoader color="#4A90E2" size={50} />
        <p>プロジェクトを読み込み中...</p>
      </div>
    );
  }

  if (projectsError) {
    return <div className="error">{projectsError}</div>;
  }

  return (
    <div className="dashboard-container">
      <h1 className="page-title">進捗予測</h1>
      <p className="page-subtitle">プロジェクトおよび個別課題の進捗予測分析</p>

      {/* Project Selector */}
      {projects.length > 0 && (
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}>
          <label style={{ marginRight: '10px', fontWeight: '500', display: 'block', marginBottom: '10px' }}>
            プロジェクト選択:
          </label>
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              setSelectedProject(parseInt(e.target.value));
              setSelectedIssue(null); // Reset selected issue when project changes
            }}
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              fontSize: '14px',
              cursor: 'pointer',
              width: '100%',
              maxWidth: '300px',
            }}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Overall Project Prediction */}
      <div>
        <div className="chart-card">
          <h3 className="chart-title">プロジェクト全体進捗予測</h3>
          {loadingProjectPrediction ? (
            <div className="loading-container">
              <ClipLoader color="#4A90E2" size={50} />
              <p>プロジェクト予測を読み込み中...</p>
            </div>
          ) : projectPredictionError ? (
            <div className="error">{projectPredictionError}</div>
          ) : projectPredictionData.length > 0 ? (
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={projectPredictionData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="week" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="planned"
                    stroke="#8884d8"
                    name="計画値"
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#82ca9d"
                    name="実績値"
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    stroke="#ffc658"
                    name="予測値"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">プロジェクト予測データがありません</div>
          )}
        </div>

        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          marginTop: '20px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}>
          <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>プロジェクト予測分析</h3>
          <div style={{ lineHeight: '1.8', color: '#555' }}>
            {projectPredictionSummary ? (
              <p>{projectPredictionSummary}</p>
            ) : (
              <p>プロジェクト予測サマリーがありません。</p>
            )}
          </div>
        </div>
      </div>

      {/* Issue List and Individual Issue Prediction */}
      {selectedProject && ( 
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          marginTop: '20px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}>
          <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>個別課題進捗予測</h3>
          {loadingIssues ? (
            <div className="loading-container">
              <ClipLoader color="#4A90E2" size={50} />
              <p>課題を読み込み中...</p>
            </div>
          ) : issuesError ? (
            <div className="error">{issuesError}</div>
          ) : issues.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '10px', marginBottom: '20px' }}>
              {issues.map((issue) => (
                <button
                  key={issue.id}
                  onClick={() => setSelectedIssue(issue.id)}
                  style={{
                    padding: '15px',
                    borderRadius: '6px',
                    border: selectedIssue === issue.id ? '2px solid #50c878' : '1px solid #ddd',
                    backgroundColor: selectedIssue === issue.id ? '#f0f9f6' : '#fff',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: selectedIssue === issue.id ? '600' : '500',
                    color: selectedIssue === issue.id ? '#50c878' : '#333',
                    transition: 'all 0.3s ease',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ fontWeight: '600', marginBottom: '5px' }}>#{issue.id} {issue.subject}</div>
                  <div style={{ fontSize: '12px', color: '#999' }}>Status: {issue.status?.name || 'N/A'}</div>
                  <div style={{ fontSize: '12px', color: '#999' }}>Due: {issue.due_date || 'N/A'}</div>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state">このプロジェクトには課題がありません。</div>
          )}

          {selectedIssue && (
            <div className="chart-card">
              <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>課題 #{selectedIssue} 進捗予測</h3>
              {loadingIssuePrediction ? (
                <div className="loading-container">
                  <ClipLoader color="#4A90E2" size={50} />
                  <p>課題予測を読み込み中...</p>
                </div>
              ) : issuePredictionError ? (
                <div className="error">{issuePredictionError}</div>
              ) : issuePredictionData.length > 0 ? (
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height={400}>
                    <LineChart data={issuePredictionData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="week" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="planned"
                        stroke="#8884d8"
                        name="計画値"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="actual"
                        stroke="#82ca9d"
                        name="実績値"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="predicted"
                        stroke="#ffc658"
                        name="予測値"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="empty-state">課題予測データがありません</div>
              )}
            </div>
          )}

          {selectedIssue && (
            <div style={{
              backgroundColor: 'white',
              borderRadius: '8px',
              padding: '20px',
              marginTop: '20px',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
            }}>
              <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>課題 #{selectedIssue} 予測分析</h3>
              <div style={{ lineHeight: '1.8', color: '#555' }}>
                {issuePredictionSummary ? (
                  <p>{issuePredictionSummary}</p>
                ) : (
                  <p>課題予測サマリーがありません。</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ProgressPrediction;