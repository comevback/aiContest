import React, { useState, useEffect } from 'react';
import { getProjects, exportData } from '../utils/api';

const DataManagement = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [exportStatus, setExportStatus] = useState(null);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await getProjects();
      if (data.error) {
        setError(data.error);
      } else if (data.projects) {
        setProjects(data.projects);
        if (data.projects.length > 0) {
          setSelectedProject(data.projects[0].id);
        }
      }
    } catch (err) {
      setError('プロジェクトの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format) => {
    if (!selectedProject) {
      setExportStatus('プロジェクトを選択してください。');
      return;
    }
    setExportStatus(`${format.toUpperCase()} 形式でエクスポートしています...`);
    try {
      const result = await exportData(selectedProject, format);
      if (result.error) {
        setExportStatus(`エクスポート失敗: ${result.error}`);
      } else {
        setExportStatus(`${format.toUpperCase()} 形式でのエクスポートが完了しました: ${result.message}`);
      }
    } catch (err) {
      setExportStatus(`エクスポート中にエラーが発生しました: ${err.message}`);
      console.error(err);
    }
  };


  return (
    <div className="dashboard-container">
      <h1 className="page-title">データ管理</h1>
      <p className="page-subtitle">プロジェクトデータのエクスポートと管理</p>

      {error && <div className="error">{error}</div>}
      {exportStatus && (
        <div style={{
          backgroundColor: '#e8f5e9',
          color: '#2e7d32',
          padding: '15px',
          borderRadius: '8px',
          marginBottom: '20px',
        }}>
          {exportStatus}
        </div>
      )}

      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '20px',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
      }}>
        <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>プロジェクト選択</h3>
        <label style={{ marginRight: '10px', fontWeight: '500', display: 'block', marginBottom: '10px' }}>
          プロジェクト:
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
            marginBottom: '20px',
          }}
        >
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '20px',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
      }}>
        <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>データエクスポート</h3>
        <p style={{ marginBottom: '15px', color: '#666' }}>
          選択したプロジェクトのデータを様々な形式でエクスポートできます。
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
          <button
            onClick={() => handleExport('csv')}
            style={{
              padding: '12px 20px',
              backgroundColor: '#4a90e2',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'background-color 0.3s ease',
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#3a7bc8'}
            onMouseLeave={(e) => e.target.style.backgroundColor = '#4a90e2'}
          >
            CSV でエクスポート
          </button>
          <button
            onClick={() => handleExport('excel')}
            style={{
              padding: '12px 20px',
              backgroundColor: '#50c878',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'background-color 0.3s ease',
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#40b867'}
            onMouseLeave={(e) => e.target.style.backgroundColor = '#50c878'}
          >
            Excel でエクスポート
          </button>
          <button
            onClick={() => handleExport('json')}
            style={{
              padding: '12px 20px',
              backgroundColor: '#f5a623',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'background-color 0.3s ease',
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#e59512'}
            onMouseLeave={(e) => e.target.style.backgroundColor = '#f5a623'}
          >
            JSON でエクスポート
          </button>
          <button
            onClick={() => handleExport('pdf')}
            style={{
              padding: '12px 20px',
              backgroundColor: '#9b59b6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
              transition: 'background-color 0.3s ease',
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#8b49a6'}
            onMouseLeave={(e) => e.target.style.backgroundColor = '#9b59b6'}
          >
            PDF でエクスポート
          </button>
        </div>
      </div>

      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '20px',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
      }}>
        <h3 style={{ marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>データ統計</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
          <div style={{
            padding: '15px',
            backgroundColor: '#f5f5f5',
            borderRadius: '6px',
            borderLeft: '4px solid #4a90e2',
          }}>
            <div style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>プロジェクト数</div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#333' }}>{projects.length}</div>
          </div>
          <div style={{
            padding: '15px',
            backgroundColor: '#f5f5f5',
            borderRadius: '6px',
            borderLeft: '4px solid #50c878',
          }}>
            <div style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>最終更新</div>
            <div style={{ fontSize: '14px', color: '#333' }}>2025年10月21日</div>
          </div>
          <div style={{
            padding: '15px',
            backgroundColor: '#f5f5f5',
            borderRadius: '6px',
            borderLeft: '4px solid #f5a623',
          }}>
            <div style={{ fontSize: '12px', color: '#999', marginBottom: '5px' }}>ストレージ使用量</div>
            <div style={{ fontSize: '14px', color: '#333' }}>2.3 MB</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataManagement;

