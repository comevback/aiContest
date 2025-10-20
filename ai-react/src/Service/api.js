const API_BASE_URL = 'http://localhost:8000'; // 后端服务器地址

export const getProjects = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/projects`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'An unknown error occurred.');
    }

    return await response.json();
  } catch (error) {
    console.error("Error calling getProjects API:", error);
    throw error;
  }
};

export const analyzeProject = async (projectId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ project_id: projectId }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'An unknown error occurred.');
    }

    return await response.json();
  } catch (error) {
    console.error("Error calling analyze API:", error);
    throw error;
  }
};
