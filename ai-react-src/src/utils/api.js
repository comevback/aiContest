import axios from 'axios';

const API_BASE = 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getProjects = async () => {
  try {
    const response = await apiClient.get('/api/projects');
    return response.data;
  } catch (error) {
    console.error('Error fetching projects:', error);
    return { error: error.message || 'Failed to fetch projects' };
  }
};

export const getIssues = async (projectId) => {
  try {
    const response = await apiClient.get(`/api/projects/${projectId}/issues`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching issues for project ${projectId}:`, error);
    return { error: error.message || 'Failed to fetch issues' };
  }
};

export const analyzeProject = async (projectIdentifier) => {
  try {
    const response = await apiClient.post('/api/analyze', {
      project_id: projectIdentifier,
    });
    return response.data;
  } catch (error) {
    console.error('Error analyzing project:', error);
    return { error: error.message || 'Failed to analyze project' };
  }
};

export const exportData = async (projectId, format) => {
  try {
    const response = await apiClient.get(`/api/projects/${projectId}/export/${format}`, {
      responseType: 'blob', // Important: tell axios to expect a binary response
    });

    // Check if the response is a file download or an error message
    const contentType = response.headers['content-type'];
    if (contentType && (contentType.includes('application/json') || contentType.includes('text/csv'))) {
      // If it's a file, trigger download
      const contentDisposition = response.headers['content-disposition'];
      let filename = `project_${projectId}_issues.${format}`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1];
        }
      }

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      return { message: `${format.toUpperCase()} 形式でのエクスポートが完了しました。` };
    } else {
      // If it's not a file, it might be an error message (e.g., for unimplemented formats)
      // In this case, response.data is a Blob, so we need to read it as text
      const errorText = await response.data.text();
      try {
        const errorJson = JSON.parse(errorText); // Assuming error messages are JSON
        return { error: errorJson.message || 'エクスポート中に不明なエラーが発生しました。' };
      } catch (parseError) {
        return { error: errorText || 'エクスポート中に不明なエラーが発生しました。' };
      }
    }
  } catch (error) {
    console.error(`Error exporting data for project ${projectId} in ${format} format:`, error);
    // If the error response is a Blob, try to parse it as JSON
    if (error.response && error.response.data instanceof Blob) {
      const errorText = await error.response.data.text();
      try {
        const errorJson = JSON.parse(errorText);
        return { error: errorJson.detail || error.message || 'エクスポート中にエラーが発生しました。' };
      } catch (parseError) {
        return { error: errorText || error.message || 'エクスポート中にエラーが発生しました。' };
      }
    }
    return { error: error.message || 'Failed to export data' };
  }
};

export const getProjectProgressPrediction = async (projectId) => {
  try {
    const response = await apiClient.get(`/api/projects/${projectId}/progress-prediction`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching project progress prediction for project ${projectId}:`, error);
    return { error: error.message || 'Failed to fetch project progress prediction' };
  }
};

export const getIssueProgressPrediction = async (issueId) => {
  try {
    const response = await apiClient.get(`/api/issues/${issueId}/progress-prediction`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching issue progress prediction for issue ${issueId}:`, error);
    return { error: error.message || 'Failed to fetch issue progress prediction' };
  }
};

export default apiClient;
