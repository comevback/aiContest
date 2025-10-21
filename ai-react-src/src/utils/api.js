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

export default apiClient;

