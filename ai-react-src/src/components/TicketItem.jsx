import React from 'react';

const TicketItem = ({ ticket }) => {
  const getStatusClass = (status) => {
    if (!status) return 'tag-open';
    const statusLower = status.toLowerCase();
    if (statusLower.includes('open') || statusLower.includes('新')) return 'tag-open';
    if (statusLower.includes('progress') || statusLower.includes('進行')) return 'tag-in-progress';
    if (statusLower.includes('closed') || statusLower.includes('完了') || statusLower.includes('解決')) return 'tag-completed';
    return 'tag-open';
  };

  const getPriorityClass = (priority) => {
    if (!priority) return 'tag-priority-medium';
    const priorityLower = priority.toLowerCase();
    if (priorityLower.includes('high') || priorityLower.includes('高')) return 'tag-priority-high';
    if (priorityLower.includes('low') || priorityLower.includes('低')) return 'tag-priority-low';
    return 'tag-priority-medium';
  };

  const statusText = ticket.status?.name || ticket.status || 'オープン';
  const priorityText = ticket.priority?.name || ticket.priority || '中';

  return (
    <div className="ticket-item">
      <div className="ticket-info">
        <div className="ticket-id">#{ticket.id}</div>
        <div className="ticket-title">{ticket.subject || ticket.title || 'No Title'}</div>
        <div className="ticket-meta">
          <span className={`ticket-tag ${getStatusClass(statusText)}`}>
            {statusText}
          </span>
          <span className={`ticket-tag ${getPriorityClass(priorityText)}`}>
            {priorityText}
          </span>
        </div>
      </div>
      <div className="ticket-arrow">›</div>
    </div>
  );
};

export default TicketItem;

