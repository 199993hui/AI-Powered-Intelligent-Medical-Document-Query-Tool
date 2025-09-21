import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import { DataObject } from '@mui/icons-material';

interface ExtractionResult {
  confidence: number;
  medical_fields: Record<string, any>;
  key_findings: string[];
  extracted_text?: string;
}

interface ExtractionResultsProps {
  open: boolean;
  onClose: () => void;
  documentId: string;
  filename: string;
  result?: ExtractionResult;
  loading?: boolean;
}

const ExtractionResults: React.FC<ExtractionResultsProps> = ({
  open,
  onClose,
  documentId,
  filename,
  result,
  loading = false,
}) => {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { height: '80vh' }
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <DataObject />
        <Typography variant="h6">Extraction Results - {filename}</Typography>
      </DialogTitle>
      
      <DialogContent>
        {loading ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography>Extracting medical data...</Typography>
          </Box>
        ) : result ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Extraction Confidence
                </Typography>
                <Chip 
                  label={`${Math.round(result.confidence * 100)}%`}
                  color={result.confidence > 0.8 ? 'success' : result.confidence > 0.6 ? 'warning' : 'error'}
                />
              </CardContent>
            </Card>

            {result.key_findings && result.key_findings.length > 0 && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Key Findings
                  </Typography>
                  <List>
                    {result.key_findings.map((finding, index) => (
                      <ListItem key={index}>
                        <ListItemText primary={finding} />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            )}

            {result.medical_fields && Object.keys(result.medical_fields).length > 0 && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Medical Fields
                  </Typography>
                  {Object.entries(result.medical_fields).map(([key, value], index) => (
                    <Box key={key}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
                        <Typography variant="body2" fontWeight="medium">
                          {key.replace('_', ' ').toUpperCase()}
                        </Typography>
                        <Typography variant="body2">
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </Typography>
                      </Box>
                      {index < Object.entries(result.medical_fields).length - 1 && <Divider />}
                    </Box>
                  ))}
                </CardContent>
              </Card>
            )}
          </Box>
        ) : (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              No extraction results available
            </Typography>
          </Box>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default ExtractionResults;