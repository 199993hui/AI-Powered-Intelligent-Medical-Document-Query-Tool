import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Button,
  Paper,
  Typography,
  LinearProgress,
  Chip,
  FormGroup,
  FormControlLabel,
  Checkbox,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Alert,
} from '@mui/material';
import { CloudUpload, Description, CheckCircle, Error } from '@mui/icons-material';
import { useDocuments } from '../hooks/useDocuments';

interface UploadFile {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
  result?: any;
}

const DocumentUpload: React.FC = () => {
  const [dragActive, setDragActive] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const { refreshDocuments } = useDocuments();
  
  const isUploading = uploadFiles.some(f => f.status === 'uploading');
  const hasPendingFiles = uploadFiles.some(f => f.status === 'pending');

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isUploading) return; // Disable drag during upload
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, [isUploading]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (isUploading) return; // Disable drop during upload

    const files = Array.from(e.dataTransfer.files).filter(
      file => file.type === 'application/pdf'
    );
    const newUploadFiles = files.map(file => ({
      file,
      progress: 0,
      status: 'pending' as const
    }));
    setUploadFiles(prev => [...prev, ...newUploadFiles]);
  }, [isUploading]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (isUploading) return; // Disable file select during upload
    if (e.target.files) {
      const files = Array.from(e.target.files);
      const newUploadFiles = files.map(file => ({
        file,
        progress: 0,
        status: 'pending' as const
      }));
      setUploadFiles(prev => [...prev, ...newUploadFiles]);
    }
  }, [isUploading]);

  const handleCategoryChange = (category: string) => {
    if (isUploading) return; // Disable category change during upload
    setSelectedCategories(prev => 
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  useEffect(() => {
    // Fallback categories in case backend is not available
    const fallbackCategories = [
      'patient_records',
      'clinical_guidelines',
      'research_papers',
      'lab_results',
      'medication_schedules'
    ];

    fetch('http://localhost:8000/api/categories')
      .then(res => {
        if (!res.ok) {
          console.error('Failed to fetch categories');
          return { categories: [] };
        }
        return res.json();
      })
      .then(data => {
        if (data.categories && data.categories.length > 0) {
          setAvailableCategories(data.categories);
        } else {
          setAvailableCategories(fallbackCategories);
        }
      })
      .catch(err => {
        console.error('Failed to fetch categories, using fallback:', err);
        setAvailableCategories(fallbackCategories);
      });
  }, []);

  const removeFile = (index: number) => {
    setUploadFiles(prev => prev.filter((_, i) => i !== index));
  };

  const uploadFile = async (uploadFile: UploadFile) => {
    const { file } = uploadFile;
    
    setUploadFiles(prev => prev.map(f => 
      f.file === file ? { ...f, status: 'uploading' } : f
    ));

    const formData = new FormData();
    formData.append('file', file);
    selectedCategories.forEach(category => {
      formData.append('categories', category);
    });

    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100);
          setUploadFiles(prev => prev.map(f => 
            f.file === file ? { ...f, progress } : f
          ));
        }
      });
      
      xhr.addEventListener('load', () => {
        console.log('Upload response status:', xhr.status);
        console.log('Upload response text:', xhr.responseText);
        
        if (xhr.status === 200) {
          const result = JSON.parse(xhr.responseText);
          setUploadFiles(prev => {
            const updated = prev.map(f => 
              f.file === file ? { ...f, status: 'completed' as const, progress: 100, result } : f
            );
            // Check if all files are done and clear categories
            const allDone = updated.every(f => f.status === 'completed' || f.status === 'error');
            if (allDone) {
              setTimeout(() => setSelectedCategories([]), 500);
            }
            return updated;
          });
          refreshDocuments();
          resolve();
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            setUploadFiles(prev => {
              const updated = prev.map(f => 
                f.file === file ? { ...f, status: 'error' as const, error: error.error || 'Upload failed' } : f
              );
              // Check if all files are done and clear categories
              const allDone = updated.every(f => f.status === 'completed' || f.status === 'error');
              if (allDone) {
                setTimeout(() => setSelectedCategories([]), 500);
              }
              return updated;
            });
            reject(error.error || 'Upload failed');
          } catch (parseError) {
            setUploadFiles(prev => {
              const updated = prev.map(f => 
                f.file === file ? { ...f, status: 'error' as const, error: `HTTP ${xhr.status}: ${xhr.responseText}` } : f
              );
              // Check if all files are done and clear categories
              const allDone = updated.every(f => f.status === 'completed' || f.status === 'error');
              if (allDone) {
                setTimeout(() => setSelectedCategories([]), 500);
              }
              return updated;
            });
            reject(`HTTP ${xhr.status}: ${xhr.responseText}`);
          }
        }
      });
      
      xhr.addEventListener('error', (event) => {
        console.error('Upload error event:', event);
        setUploadFiles(prev => {
          const updated = prev.map(f => 
            f.file === file ? { ...f, status: 'error' as const, error: 'Network error - check if backend is running' } : f
          );
          // Check if all files are done and clear categories
          const allDone = updated.every(f => f.status === 'completed' || f.status === 'error');
          if (allDone) {
            setTimeout(() => setSelectedCategories([]), 500);
          }
          return updated;
        });
        reject('Network error - check if backend is running');
      });
      
      xhr.open('POST', 'http://localhost:8000/api/documents/upload');
      xhr.send(formData);
    });
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0 || selectedCategories.length === 0) return;

    const pendingFiles = uploadFiles.filter(f => f.status === 'pending');
    
    for (const uploadFileItem of pendingFiles) {
      try {
        await uploadFile(uploadFileItem);
      } catch (error) {
        console.error('Upload failed:', error);
      }
    }
    

  };

  return (
    <Paper sx={{ p: 3, mb: 2 }}>
      <Typography variant="h6" gutterBottom>
        Upload Medical Documents
      </Typography>

      <Box
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        sx={{
          border: 2,
          borderColor: dragActive ? 'primary.main' : 'grey.300',
          borderStyle: 'dashed',
          borderRadius: 2,
          p: 4,
          textAlign: 'center',
          backgroundColor: dragActive ? 'action.hover' : 'background.paper',
          cursor: isUploading ? 'not-allowed' : 'pointer',
          opacity: isUploading ? 0.6 : 1,
          mb: 2,
        }}
      >
        <input
          type="file"
          multiple
          accept=".pdf"
          onChange={handleFileSelect}
          disabled={isUploading}
          style={{ display: 'none' }}
          id="file-upload"
        />
        <label htmlFor="file-upload">
          <CloudUpload sx={{ fontSize: 48, color: 'grey.400', mb: 1 }} />
          <Typography variant="h6" color="textSecondary">
            Drag and drop PDF files here, or click to select
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Supports multiple PDF files up to 200MB each
          </Typography>
        </label>
      </Box>

      {/* Category Selection */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1" gutterBottom>
          Medical Categories {availableCategories.length === 0 && '(Loading...)'}
        </Typography>
        {availableCategories.length > 0 ? (
          <FormGroup row>
            {availableCategories.map((category) => (
              <FormControlLabel
                key={category}
                control={
                  <Checkbox
                    checked={selectedCategories.includes(category)}
                    onChange={() => handleCategoryChange(category)}
                    disabled={isUploading}
                  />
                }
                label={category.replace('_', ' ').toUpperCase()}
              />
            ))}
          </FormGroup>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Loading categories...
          </Typography>
        )}
        {selectedCategories.length > 0 && (
          <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {selectedCategories.map((category) => (
              <Chip 
                key={category} 
                label={category.replace('_', ' ')} 
                size="small" 
                onDelete={() => handleCategoryChange(category)}
              />
            ))}
          </Box>
        )}
      </Box>

      {uploadFiles.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Files ({uploadFiles.length}):
          </Typography>
          <List>
            {uploadFiles.map((uploadFile, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  {uploadFile.status === 'completed' ? (
                    <CheckCircle color="success" />
                  ) : uploadFile.status === 'error' ? (
                    <Error color="error" />
                  ) : (
                    <Description />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary={uploadFile.file.name}
                  secondary={
                    <Box>
                      <Typography variant="body2">
                        {(uploadFile.file.size / 1024 / 1024).toFixed(1)}MB
                      </Typography>
                      {uploadFile.status === 'uploading' && (
                        <LinearProgress 
                          variant="determinate" 
                          value={uploadFile.progress} 
                          sx={{ mt: 1 }}
                        />
                      )}
                      {uploadFile.status === 'error' && (
                        <Alert severity="error" sx={{ mt: 1 }}>
                          {uploadFile.error}
                        </Alert>
                      )}
                    </Box>
                  }
                />
                {uploadFile.status === 'pending' && !uploadFiles.some(f => f.status === 'uploading') && (
                  <Button onClick={() => removeFile(index)} size="small">
                    Remove
                  </Button>
                )}
              </ListItem>
            ))}
          </List>
        </Box>
      )}



      <Button
        variant="contained"
        onClick={handleUpload}
        disabled={!hasPendingFiles || selectedCategories.length === 0 || isUploading}
        startIcon={<CloudUpload />}
      >
        {uploadFiles.some(f => f.status === 'uploading') ? 'Uploading...' : `Upload ${uploadFiles.filter(f => f.status === 'pending').length} File(s)`}
      </Button>
    </Paper>
  );
};

export default DocumentUpload;