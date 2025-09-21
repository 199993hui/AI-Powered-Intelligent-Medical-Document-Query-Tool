import React from 'react';
import {
  Toolbar,
  Typography,
  Button,
  Box,
} from '@mui/material';
import {
  Delete,
  GetApp,
  Edit,
} from '@mui/icons-material';

interface BulkActionsProps {
  selectedCount: number;
  onBulkDelete: () => void;
  onBulkExport: () => void;
  onBulkEdit: () => void;
}

const BulkActions: React.FC<BulkActionsProps> = ({
  selectedCount,
  onBulkDelete,
  onBulkExport,
  onBulkEdit,
}) => {
  if (selectedCount === 0) return null;

  return (
    <Toolbar sx={{ bgcolor: 'primary.light', color: 'primary.contrastText' }}>
      <Typography variant="h6" sx={{ flex: 1 }}>
        {selectedCount} document{selectedCount > 1 ? 's' : ''} selected
      </Typography>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          startIcon={<Edit />}
          onClick={onBulkEdit}
          color="inherit"
          variant="outlined"
        >
          Edit Categories
        </Button>
        <Button
          startIcon={<GetApp />}
          onClick={onBulkExport}
          color="inherit"
          variant="outlined"
        >
          Export
        </Button>
        <Button
          startIcon={<Delete />}
          onClick={onBulkDelete}
          color="inherit"
          variant="outlined"
        >
          Delete
        </Button>
      </Box>
    </Toolbar>
  );
};

export default BulkActions;