import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box } from '@mui/material';
import { DocumentProvider } from './contexts/DocumentContext';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import DocumentManagement from './pages/DocumentManagement';
import SearchEngine from './pages/SearchEngine';
import Settings from './pages/Settings';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <DocumentProvider>
          <Box sx={{ display: 'flex', minHeight: '100vh' }}>
            <Navigation />
            <Box component="main" sx={{ flexGrow: 1, backgroundColor: '#f8fafc' }}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/documents" element={<DocumentManagement />} />
                <Route path="/search" element={<SearchEngine />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </Box>
          </Box>
        </DocumentProvider>
      </Router>
    </ThemeProvider>
  );
}

export default App;
