import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import Header from '../components/Header';
import DocumentTable from '../components/DocumentTable';
import DocumentUpload from '../components/DocumentUpload';

const DocumentManagement: React.FC = () => {
  return (
    <Box>
      <Header />
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" sx={{ mb: 3, fontWeight: 'bold' }}>
          Document Management
        </Typography>
        
        <Box sx={{ mb: 3 }}>
          <DocumentUpload />
        </Box>
        <Paper sx={{ p: 2 }}>
          <DocumentTable />
        </Paper>
      </Box>
    </Box>
  );
};

export default DocumentManagement;