import axios from 'axios';
import { DocumentsResponse } from '../types/document';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const documentApi = {
  // Get documents with filtering and pagination
  getDocuments: async (): Promise<DocumentsResponse> => {
    const response = await api.get('/api/documents');
    return response.data;
  },

  // Get available categories
  getCategories: async (): Promise<string[]> => {
    const response = await api.get('/api/categories');
    return response.data.categories;
  },

  // Upload documents
  uploadDocument: async (file: File, categories: string[]): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    categories.forEach(category => {
      formData.append('categories', category);
    });

    const response = await api.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Delete document
  deleteDocument: async (id: string): Promise<void> => {
    await api.delete(`/api/documents/${id}`);
  },

  // Extract data from document
  extractDocument: async (id: string): Promise<any> => {
    const response = await api.post(`/api/documents/${id}/extract`);
    return response.data;
  },

  // Update document categories
  updateCategories: async (id: string, categories: string[]): Promise<void> => {
    await api.put(`/api/documents/${id}/categories`, { categories });
  },
};

export default api;