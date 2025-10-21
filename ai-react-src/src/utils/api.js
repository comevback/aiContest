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
    const response = await apiClient.get(`/api/projects/${projectId}/export/${format}`);
    return response.data;
  } catch (error) {
    console.error(`Error exporting data for project ${projectId} in ${format} format:`, error);
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
