import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const ProgressPrediction = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE = 'http://localhost:8000';

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE}/api/projects`);
      if (response.data.projects) {
        setProjects(response.data.projects);
        if (response.data.projects.length > 0) {
          setSelectedProject(response.data.projects[0].id);
        }
      }
    } catch (err) {
      setError('プロジェクトの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Mock data for progress prediction
  const getMockProgressData = () => {
    return [
      { week: '第1週', planned: 20, actual: 18, predicted: 18 },
      { week: '第2週', planned: 40, actual: 35, predicted: 36 },
      { week: '第3週', planned: 60, actual: 52, predicted: 58 },
      { week: '第4週', planned: 80, actual: 70, predicted: 75 },
      { week: '第5週', planned: 100, actual: null, predicted: 88 },
      { week: '第6週', planned: 100, actual: null, predicted: 98 },
    ];
  };

  const progressData = getMockProgressData();

  return (
    <div className="dashboard-container">
      <h1 className="page-title">進捗予測</h1>
      <p className="page-subtitle">プロジェクト進捗の予測分析</p>

      {error && <div className="error">{error}</div>}

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
            onChange={(e) => setSelectedProject(e.target.value)}
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

