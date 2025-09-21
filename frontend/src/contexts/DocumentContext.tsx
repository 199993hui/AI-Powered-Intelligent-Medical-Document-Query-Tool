import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { Document, DocumentFilters } from '../types/document';

interface DocumentState {
  documents: Document[];
  loading: boolean;
  error: string | null;
  total: number;
  page: number;
  limit: number;
  filters: DocumentFilters;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
}

type DocumentAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_DOCUMENTS'; payload: { documents: Document[]; total: number } }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_FILTERS'; payload: DocumentFilters }
  | { type: 'SET_PAGINATION'; payload: { page: number; limit: number } }
  | { type: 'SET_SORTING'; payload: { sortBy: string; sortOrder: 'asc' | 'desc' } }
  | { type: 'DELETE_DOCUMENT'; payload: string }
  | { type: 'UPDATE_DOCUMENT'; payload: Document };

const initialState: DocumentState = {
  documents: [],
  loading: false,
  error: null,
  total: 0,
  page: 1,
  limit: 20,
  filters: { categories: [] },
  sortBy: 'upload_date',
  sortOrder: 'desc',
};

const documentReducer = (state: DocumentState, action: DocumentAction): DocumentState => {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_DOCUMENTS':
      return { 
        ...state, 
        documents: action.payload.documents, 
        total: action.payload.total,
        loading: false,
        error: null 
      };
    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false };
    case 'SET_FILTERS':
      return { ...state, filters: action.payload, page: 1 };
    case 'SET_PAGINATION':
      return { ...state, page: action.payload.page, limit: action.payload.limit };
    case 'SET_SORTING':
      return { ...state, sortBy: action.payload.sortBy, sortOrder: action.payload.sortOrder };
    case 'DELETE_DOCUMENT':
      return { 
        ...state, 
        documents: state.documents.filter(doc => doc.id !== action.payload),
        total: state.total - 1
      };
    case 'UPDATE_DOCUMENT':
      return {
        ...state,
        documents: state.documents.map(doc => 
          doc.id === action.payload.id ? action.payload : doc
        )
      };
    default:
      return state;
  }
};

interface DocumentContextType {
  state: DocumentState;
  dispatch: React.Dispatch<DocumentAction>;
}

const DocumentContext = createContext<DocumentContextType | undefined>(undefined);

export const DocumentProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(documentReducer, initialState);

  return (
    <DocumentContext.Provider value={{ state, dispatch }}>
      {children}
    </DocumentContext.Provider>
  );
};

export const useDocumentContext = () => {
  const context = useContext(DocumentContext);
  if (context === undefined) {
    throw new Error('useDocumentContext must be used within a DocumentProvider');
  }
  return context;
};