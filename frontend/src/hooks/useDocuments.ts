import { useCallback, useEffect } from 'react';
import { useDocumentContext } from '../contexts/DocumentContext';
import { documentApi } from '../services/api';
import { DocumentFilters } from '../types/document';

export const useDocuments = () => {
  const { state, dispatch } = useDocumentContext();

  const fetchDocuments = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const response = await documentApi.getDocuments();
      dispatch({ 
        type: 'SET_DOCUMENTS', 
        payload: { documents: response.documents, total: response.total } 
      });
    } catch (error) {
      dispatch({ 
        type: 'SET_ERROR', 
        payload: error instanceof Error ? error.message : 'Failed to fetch documents' 
      });
    }
  }, [dispatch]);

  const setFilters = useCallback((filters: DocumentFilters) => {
    dispatch({ type: 'SET_FILTERS', payload: filters });
  }, [dispatch]);

  const setPagination = useCallback((page: number, limit: number) => {
    dispatch({ type: 'SET_PAGINATION', payload: { page, limit } });
  }, [dispatch]);

  const setSorting = useCallback((sortBy: string, sortOrder: 'asc' | 'desc') => {
    dispatch({ type: 'SET_SORTING', payload: { sortBy, sortOrder } });
  }, [dispatch]);

  const deleteDocument = useCallback(async (id: string) => {
    try {
      await documentApi.deleteDocument(id);
      dispatch({ type: 'DELETE_DOCUMENT', payload: id });
    } catch (error) {
      dispatch({ 
        type: 'SET_ERROR', 
        payload: error instanceof Error ? error.message : 'Failed to delete document' 
      });
    }
  }, [dispatch]);

  const uploadDocument = useCallback(async (file: File, categories: string[]) => {
    try {
      await documentApi.uploadDocument(file, categories);
      // Refresh documents after upload
      fetchDocuments();
    } catch (error) {
      dispatch({ 
        type: 'SET_ERROR', 
        payload: error instanceof Error ? error.message : 'Failed to upload document' 
      });
    }
  }, [dispatch, fetchDocuments]);

  // Auto-fetch when dependencies change
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  return {
    documents: state.documents,
    loading: state.loading,
    error: state.error,
    total: state.total,
    page: state.page,
    limit: state.limit,
    filters: state.filters,
    sortBy: state.sortBy,
    sortOrder: state.sortOrder,
    fetchDocuments,
    refreshDocuments: fetchDocuments,
    setFilters,
    setPagination,
    setSorting,
    deleteDocument,
    uploadDocument,
  };
};