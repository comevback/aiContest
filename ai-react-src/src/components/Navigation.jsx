import React from 'react';

const Navigation = ({ currentPage, setCurrentPage, onLogout }) => {
  const navItems = [
    { id: 'dashboard', label: 'ダッシュボード', icon: '', color: '#4a90e2' },
    { id: 'issue-analysis', label: '課題分析', icon: '', color: '#50c878' },
    { id: 'progress-prediction', label: '進捗予測', icon: '', color: '#f5a623' },
    { id: 'data-management', label: 'データ管理', icon: '', color: '#9b59b6' },
    { id: 'knowledge-base', label: '知識ベース', icon: '', color: '#bd10e0' },
  ];

  return (
    <nav className="navbar">
      <div className="navbar-left">
        <a href="#" className="navbar-logo" onClick={(e) => {
          e.preventDefault();
          setCurrentPage('dashboard');
        }}>
          <div className="navbar-logo-icon">SPA</div>
          <span>SPAシステム</span>
          <span className="version-badge">v0.1</span>
        </a>
      </div>
      <div className="nav-buttons">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-button ${currentPage === item.id ? 'active' : ''}`}
            onClick={() => setCurrentPage(item.id)}
            style={currentPage === item.id ? { backgroundColor: item.color } : {}}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
        {/* Add the "Switch Redmine User" button */}
        <button
          className="nav-button"
          onClick={onLogout}
          style={{ marginLeft: '20px', backgroundColor: '#e74c3c', color: 'white' }} // Example styling
        >
          <span>Log Out</span>
        </button>
      </div>
    </nav>
  );
};

export default Navigation;

