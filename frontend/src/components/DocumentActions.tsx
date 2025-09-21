import React from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
} from '@mui/material';
import {
  MoreVert,
  Visibility,
  Download,
  DataObject,
  BarChart,
  Edit,
  Delete,
} from '@mui/icons-material';

interface DocumentActionsProps {
  documentId: string;
  onView: (id: string) => void;
  onDownload: (id: string) => void;
  onExtract: (id: string) => void;
  onVisualize: (id: string) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

const DocumentActions: React.FC<DocumentActionsProps> = ({
  documentId,
  onView,
  onDownload,
  onExtract,
  onVisualize,
  onEdit,
  onDelete,
}) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleAction = (action: () => void) => {
    action();
    handleClose();
  };

  return (
    <>
      <Tooltip title="Actions">
        <IconButton onClick={handleClick} size="small">
          <MoreVert />
        </IconButton>
      </Tooltip>
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        <MenuItem onClick={() => handleAction(() => onView(documentId))}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={() => handleAction(() => onDownload(documentId))}>
          <ListItemIcon>
            <Download fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={() => handleAction(() => onExtract(documentId))}>
          <ListItemIcon>
            <DataObject fontSize="small" />
          </ListItemIcon>
          <ListItemText>Extract Data</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={() => handleAction(() => onVisualize(documentId))}>
          <ListItemIcon>
            <BarChart fontSize="small" />
          </ListItemIcon>
          <ListItemText>Visualize</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={() => handleAction(() => onEdit(documentId))}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit Categories</ListItemText>
        </MenuItem>
        
        <MenuItem onClick={() => handleAction(() => onDelete(documentId))}>
          <ListItemIcon>
            <Delete fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>
    </>
  );
};

export default DocumentActions;