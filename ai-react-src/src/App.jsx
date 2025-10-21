import React, { useState } from 'react';
import './App.css';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import IssueAnalysis from './pages/IssueAnalysis';
import ProgressPrediction from './pages/ProgressPrediction';
import DataManagement from './pages/DataManagement';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />;
      case 'issue-analysis':
        return <IssueAnalysis />;
      case 'progress-prediction':
        return <ProgressPrediction />;
      case 'data-management':
        return <DataManagement />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="app">
      <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}

export default App;

