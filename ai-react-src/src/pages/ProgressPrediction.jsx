import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getProgressPrediction } from '../utils/api';
import { ClipLoader } from 'react-spinners';

const ProgressPrediction = ({ projects, selectedProject, setSelectedProject, loadingProjects, projectsError }) => {
  const [loadingPrediction, setLoadingPrediction] = useState(false);
  const [predictionError, setPredictionError] = useState(null);
  const [progressData, setProgressData] = useState([]);

  useEffect(() => {
    if (selectedProject) {
      fetchProgressData(selectedProject);
    }
  }, [selectedProject]);

  const fetchProgressData = async (projectId) => {
    setLoadingPrediction(true);
    setPredictionError(null);
    try {
      const data = await getProgressPrediction(projectId);
      if (data.error) {
        setPredictionError(data.error);
        setProgressData([]);
      } else if (data.progress_data) {
        setProgressData(data.progress_data);
      } else {
        setProgressData([]);
      }
    } catch (err) {
      setPredictionError('進捗予測データの取得に失敗しました');
      console.error(err);
    } finally {
      setLoadingPrediction(false);
    }
  };

  if (loadingProjects || loadingPrediction) {
    return (
      <div className="loading-container">
        <ClipLoader color="#4A90E2" size={50} />
        <p>読み込み中...</p>
      </div>
    );
  }

  if (projectsError) {
    return <div className="error">{projectsError}</div>;
  }

  if (predictionError) {
    return <div className="error">{predictionError}</div>;
  }

  return (
    <div className="dashboard-container">
      <h1 className="page-title">進捗予測</h1>
      <p className="page-subtitle">プロジェクト進捗の予測分析</p>

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
            onChange={(e) => setSelectedProject(parseInt(e.target.value))}
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

      <div className="chart-card">
        <h3 className="chart-title">進捗予測グラフ</h3>
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={progressData}>
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
      </div>

      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '20px',
        marginTop: '20px',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
      }}>
        <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>予測分析</h3>
        <div style={{ lineHeight: '1.8', color: '#555' }}>
          <p>
            <strong>現在の進捗:</strong> 実績値は計画値より若干遅れていますが、予測値では第6週までに100%の完了が見込まれます。
          </p>
          <p>
            <strong>推奨アクション:</strong> 現在のペースを維持しつつ、リソースの最適化を検討してください。特に第4週から第5週への移行期に注意が必要です。
          </p>
          <p>
            <strong>リスク評価:</strong> 低リスク - 現在のトレンドでは予定通りの完了が期待できます。
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProgressPrediction;
