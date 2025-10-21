import React, { useState, useEffect } from 'react';
import SummaryCard from '../components/SummaryCard';
import TicketItem from '../components/TicketItem';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getProjects, getIssues } from '../utils/api';

const Dashboard = () => {
  const [issues, setIssues] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
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
          setSelectedProject(data.projects[0].id);
          fetchIssues(data.projects[0].id); // Fetch issues for the first project
        }
      }
    } catch (err) {
      setError('プロジェクトの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchIssues = async (projectId) => {
    try {
      setLoading(true);
      const data = await getIssues(projectId);
      if (data.error) {
        setError(data.error);
        setIssues([]);
      } else if (data.issues) {
        setIssues(data.issues);
      } else {
        setIssues([]);
      }
    } catch (err) {
      setError('課題の取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = () => {
    const stats = {
      total: issues.length,
      open: 0,
      inProgress: 0,
      completed: 0,
      overdue: 0,
    };

    issues.forEach((issue) => {
      const status = issue.status?.name?.toLowerCase() || '';
      if (status.includes('open') || status.includes('新')) stats.open++;
      if (status.includes('progress') || status.includes('進行')) stats.inProgress++;
      if (status.includes('completed') || status.includes('完了') || status.includes('解決')) stats.completed++;
    });

    stats.overdue = Math.max(0, stats.total - stats.open - stats.inProgress - stats.completed);
    return stats;
  };

  const getStatusDistribution = () => {
    const distribution = {};
    issues.forEach((issue) => {
      const status = issue.status?.name || 'Unknown';
      distribution[status] = (distribution[status] || 0) + 1;
    });

    return Object.entries(distribution).map(([name, value]) => ({
      name,
      value,
    }));
  };

  const getPriorityDistribution = () => {
    const distribution = {};
    issues.forEach((issue) => {
      const priority = issue.priority?.name || 'Medium';
      distribution[priority] = (distribution[priority] || 0) + 1;
    });

    return Object.entries(distribution).map(([name, value]) => ({
      name,
      value,
    }));
  };

  const COLORS = ['#ef4444', '#f97316', '#22c55e', '#6b7280'];
  const PRIORITY_COLORS = ['#ef4444', '#f97316', '#22c55e'];

  const stats = calculateStats();
  const statusData = getStatusDistribution();
  const priorityData = getPriorityDistribution();

  if (loading && issues.length === 0) {
    return <div className="loading">読み込み中...</div>;
  }

  return (
    <div className="dashboard-container">
      <h1 className="page-title">プロジェクトダッシュボード</h1>
      <p className="page-subtitle">Redmineチケット状況の可視化</p>

      {error && <div className="error">{error}</div>}

      {/* Project Selector */}
      {projects.length > 0 && (
        <div style={{ marginBottom: '30px', backgroundColor: 'white', borderRadius: '8px', padding: '20px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
          <label style={{ marginRight: '10px', fontWeight: '500', display: 'block', marginBottom: '10px' }}>プロジェクト選択:</label>
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              setSelectedProject(e.target.value);
              fetchIssues(e.target.value);
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

      {/* Summary Cards */}
      <div className="summary-cards">
        <SummaryCard
          label="総チケット数"
          value={stats.total}
          icon="📋"
          iconColor="icon-blue"
        />
        <SummaryCard
          label="進行中"
          value={stats.inProgress}
          icon="▶"
          iconColor="icon-orange"
        />
        <SummaryCard
          label="完了済み"
          value={stats.completed}
          icon="✓"
          iconColor="icon-green"
        />
        <SummaryCard
          label="期限超過"
          value={stats.overdue}
          icon="⚠"
          iconColor="icon-red"
        />
      </div>

      {/* Charts */}
      <div className="charts-container">
        <div className="chart-card">
          <h3 className="chart-title">チケットステータス分布</h3>
          <div className="chart-wrapper">
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">データなし</div>
            )}
          </div>
        </div>

        <div className="chart-card">
          <h3 className="chart-title">優先度別チケット数</h3>
          <div className="chart-wrapper">
            {priorityData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={priorityData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="#8884d8">
                    {priorityData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={PRIORITY_COLORS[index % PRIORITY_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">データなし</div>
            )}
          </div>
        </div>
      </div>

      {/* Latest Tickets */}
      <div className="latest-tickets-container">
        <h3 className="latest-tickets-title">最新のチケット</h3>
        {issues.length > 0 ? (
          issues.slice(0, 5).map((ticket) => (
            <TicketItem key={ticket.id} ticket={ticket} />
          ))
        ) : (
          <div className="empty-state">チケットがありません</div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;

