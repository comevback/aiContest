import axios from 'axios';

const API_BASE = 'http://localhost:8000';

let redmineUrl = '';
let redmineApiKey = '';

export const setRedmineCredentials = (url, apiKey) => {
  redmineUrl = url;
  redmineApiKey = apiKey;
};

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add an interceptor to include Redmine credentials in headers
apiClient.interceptors.request.use(
  (config) => {
    if (redmineUrl && redmineApiKey) {
      config.headers['X-Redmine-Url'] = redmineUrl;
      config.headers['X-Redmine-Api-Key'] = redmineApiKey;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// --- RAG Functions ---

export const getDocuments = async () => {
  try {
    const response = await apiClient.get('/api/rag/documents');
    return response.data;
  } catch (error) {
    console.error('Error fetching documents:', error);
    return { error: error.response?.data?.detail || error.message || 'Failed to fetch documents' };
  }
};

export const deleteDocument = async (filename) => {
  try {
    const response = await apiClient.delete(`/api/rag/documents/${filename}`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting document ${filename}:`, error);
    return { error: error.response?.data?.detail || error.message || 'Failed to delete document' };
  }
};

export const uploadRAGFiles = async (files) => {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });

  try {
    // Use a separate axios instance for multipart/form-data
    const response = await axios.post(`${API_BASE}/api/rag/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    console.error('Error uploading RAG files:', error);
    return { error: error.response?.data?.detail || error.message || 'Failed to upload files' };
  }
};

export const getIndexingProgress = async (taskId) => {
  try {
    const response = await apiClient.get(`/api/rag/progress/${taskId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching indexing progress for task ${taskId}:`, error);
    return { error: error.response?.data?.detail || error.message || 'Failed to fetch progress' };
  }
};

export const reloadRAG = async () => {
  try {
    const response = await apiClient.post('/api/rag/reload');
    return response.data;
  } catch (error) {
    console.error('Error reloading RAG service:', error);
    return { error: error.response?.data?.detail || error.message || 'Failed to reload RAG service' };
  }
};

export const askRAG = async (question) => {
  try {
    const response = await apiClient.post('/api/chat', { question });
    return response.data;
  } catch (error) {
    console.error('Error in RAG chat:', error);
    return { error: error.response?.data?.detail || error.message || 'Failed to get answer from RAG chat' };
  }
};


// --- Existing Redmine Functions ---

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

export const updateWikiPage = async (projectIdentifier, title, content) => {
  try {
    const response = await apiClient.post(`/api/projects/${projectIdentifier}/wiki`, {
      title,
      content,
      comment: 'Updated by AI analysis tool',
    });
    return response.data;
  } catch (error) {
    console.error('Error updating wiki page:', error);
    if (error.response && error.response.data && error.response.data.detail) {
      return { error: error.response.data.detail };
    }
    return { error: error.message || 'Failed to update wiki page' };
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
