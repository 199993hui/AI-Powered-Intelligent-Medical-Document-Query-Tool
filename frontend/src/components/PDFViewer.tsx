import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  IconButton,
} from '@mui/material';
import { Close, Download } from '@mui/icons-material';

interface PDFViewerProps {
  open: boolean;
  onClose: () => void;
  documentId: string;
  filename: string;
}

const PDFViewer: React.FC<PDFViewerProps> = ({
  open,
  onClose,
  documentId,
  filename,
}) => {
  const handleDownload = () => {
    // Implement download functionality
    console.log('Download document:', documentId);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '90vh' }
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6">{filename}</Typography>
        <Box>
          <IconButton onClick={handleDownload}>
            <Download />
          </IconButton>
          <IconButton onClick={onClose}>
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <DialogContent sx={{ p: 0, height: '100%' }}>
        <Box sx={{ 
          height: '100%', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          bgcolor: 'grey.100'
        }}>
          <Typography color="text.secondary">
            PDF Viewer - Implementation pending
          </Typography>
        </Box>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default PDFViewer;