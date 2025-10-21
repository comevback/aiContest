import React from 'react';

const SummaryCard = ({ label, value, icon, iconColor }) => {
  return (
    <div className="summary-card">
      <div className="summary-card-content">
        <div className="summary-card-label">{label}</div>
        <div className="summary-card-value">{value}</div>
      </div>
      <div className={`summary-card-icon ${iconColor}`}>
        {icon}
      </div>
    </div>
  );
};

export default SummaryCard;

