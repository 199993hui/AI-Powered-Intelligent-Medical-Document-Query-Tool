import React, { useState, useMemo } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  TableSortLabel,
  Checkbox,
  IconButton,
  Chip,
  Typography,
  LinearProgress,
  Alert,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  Toolbar,
  Stack,
} from '@mui/material';
import {
  MoreVert,
  Visibility,
  Download,
  DataObject,
  BarChart,
  Edit,
  Delete,
  Clear,
} from '@mui/icons-material';
import { useDocuments } from '../hooks/useDocuments';
import { Document } from '../types/document';

const DocumentTable: React.FC = () => {
  const {
    documents,
    loading,
    error,
    page,
    limit,
    sortBy,
    sortOrder,
    setPagination,
    setSorting,
    deleteDocument,
  } = useDocuments();

  const [selected, setSelected] = useState<string[]>([]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null);
  
  // Filter states
  const [searchFilter, setSearchFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
  const [dateFromFilter, setDateFromFilter] = useState('');
  const [dateToFilter, setDateToFilter] = useState('');
  
  // Available categories from documents
  const availableCategories = useMemo(() => {
    const cats = new Set<string>();
    documents.forEach(doc => doc.categories.forEach(cat => cats.add(cat)));
    return Array.from(cats).sort();
  }, [documents]);
  
  // Filtered documents
  const filteredDocuments = useMemo(() => {
    return documents.filter(doc => {
      // Search filter
      if (searchFilter && !doc.filename.toLowerCase().includes(searchFilter.toLowerCase())) {
        return false;
      }
      
      // Category filter
      if (categoryFilter.length > 0 && !categoryFilter.some(cat => doc.categories.includes(cat))) {
        return false;
      }
      
      // Date range filter
      if (dateFromFilter) {
        const docDate = new Date(doc.upload_date);
        const fromDate = new Date(dateFromFilter);
        if (docDate < fromDate) return false;
      }
      
      if (dateToFilter) {
        const docDate = new Date(doc.upload_date);
        const toDate = new Date(dateToFilter);
        toDate.setHours(23, 59, 59, 999); // End of day
        if (docDate > toDate) return false;
      }
      
      return true;
    });
  }, [documents, searchFilter, categoryFilter, dateFromFilter, dateToFilter]);
  


  const handleSelectAllClick = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelected = filteredDocuments.map((doc) => doc.id);
      setSelected(newSelected);
    } else {
      setSelected([]);
    }
  };

  const handleClick = (id: string) => {
    const selectedIndex = selected.indexOf(id);
    let newSelected: string[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selected, id);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selected.slice(1));
    } else if (selectedIndex === selected.length - 1) {
      newSelected = newSelected.concat(selected.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selected.slice(0, selectedIndex),
        selected.slice(selectedIndex + 1)
      );
    }
    setSelected(newSelected);
  };

  const handleChangePage = (_: unknown, newPage: number) => {
    setPagination(newPage + 1, limit);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPagination(1, parseInt(event.target.value, 10));
  };

  const handleRequestSort = (property: string) => {
    const isAsc = sortBy === property && sortOrder === 'asc';
    setSorting(property, isAsc ? 'desc' : 'asc');
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, document: Document) => {
    setAnchorEl(event.currentTarget);
    setSelectedDocument(document);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedDocument(null);
  };

  const handleDeleteClick = (document: Document) => {
    setDocumentToDelete(document);
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (documentToDelete) {
      await deleteDocument(documentToDelete.id);
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
    }
  };



  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const clearFilters = () => {
    setSearchFilter('');
    setCategoryFilter([]);
    setDateFromFilter('');
    setDateToFilter('');
  };
  
  const isSelected = (id: string) => selected.indexOf(id) !== -1;

  if (loading) {
    return (
      <Box>
        <LinearProgress />
        <Typography sx={{ mt: 2, textAlign: 'center' }}>Loading documents...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      {/* Filter Toolbar */}
      <Paper sx={{ mb: 2 }}>
        <Toolbar sx={{ gap: 2, flexWrap: 'wrap', py: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Documents ({filteredDocuments.length})
          </Typography>
          
          <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', gap: 1 }}>
            <TextField
              size="small"
              placeholder="Search filename..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              sx={{ minWidth: 200 }}
            />
            
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Categories</InputLabel>
              <Select
                multiple
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value)}
                label="Categories"
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.map((value) => (
                      <Chip key={value} label={value.replace('_', ' ')} size="small" />
                    ))}
                  </Box>
                )}
              >
                {availableCategories.map((category) => (
                  <MenuItem key={category} value={category}>
                    <Checkbox checked={categoryFilter.indexOf(category) > -1} />
                    <ListItemText primary={category.replace('_', ' ')} />
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <TextField
              size="small"
              type="date"
              label="From Date"
              value={dateFromFilter}
              onChange={(e) => setDateFromFilter(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 150 }}
            />
            
            <TextField
              size="small"
              type="date"
              label="To Date"
              value={dateToFilter}
              onChange={(e) => setDateToFilter(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 150 }}
            />
            
            <Button
              variant="outlined"
              startIcon={<Clear />}
              onClick={clearFilters}
              disabled={!searchFilter && categoryFilter.length === 0 && !dateFromFilter && !dateToFilter}
            >
              Clear
            </Button>
          </Stack>
        </Toolbar>
      </Paper>

      <TableContainer component={Paper}>
        <Table sx={{ minWidth: 750 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  color="primary"
                  indeterminate={selected.length > 0 && selected.length < filteredDocuments.length}
                  checked={filteredDocuments.length > 0 && selected.length === filteredDocuments.length}
                  onChange={handleSelectAllClick}
                />
              </TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'filename'}
                  direction={sortBy === 'filename' ? sortOrder : 'asc'}
                  onClick={() => handleRequestSort('filename')}
                >
                  Filename
                </TableSortLabel>
              </TableCell>
              <TableCell>Categories</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortBy === 'upload_date'}
                  direction={sortBy === 'upload_date' ? sortOrder : 'asc'}
                  onClick={() => handleRequestSort('upload_date')}
                >
                  Upload Date
                </TableSortLabel>
              </TableCell>

              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredDocuments.map((document) => {
              const isItemSelected = isSelected(document.id);
              return (
                <TableRow
                  hover
                  onClick={() => handleClick(document.id)}
                  role="checkbox"
                  aria-checked={isItemSelected}
                  tabIndex={-1}
                  key={document.id}
                  selected={isItemSelected}
                >
                  <TableCell padding="checkbox">
                    <Checkbox color="primary" checked={isItemSelected} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {document.filename}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {document.categories.map((category) => (
                        <Chip
                          key={category}
                          label={category.replace('_', ' ')}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </TableCell>
                  <TableCell>{formatDate(document.upload_date)}</TableCell>
                  <TableCell>
                    <IconButton
                      onClick={(e) => {
                        e.stopPropagation();
                        handleMenuClick(e, document);
                      }}
                    >
                      <MoreVert />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        rowsPerPageOptions={[10, 20, 50]}
        component="div"
        count={filteredDocuments.length}
        rowsPerPage={limit}
        page={page - 1}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
      />

      {/* Action Menu */}
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleMenuClose}>
        <MenuItem onClick={handleMenuClose}>
          <ListItemIcon><Visibility /></ListItemIcon>
          <ListItemText>View</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <ListItemIcon><Download /></ListItemIcon>
          <ListItemText>Download</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <ListItemIcon><DataObject /></ListItemIcon>
          <ListItemText>Extract Data</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <ListItemIcon><BarChart /></ListItemIcon>
          <ListItemText>Visualize</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <ListItemIcon><Edit /></ListItemIcon>
          <ListItemText>Edit Categories</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => selectedDocument && handleDeleteClick(selectedDocument)}>
          <ListItemIcon><Delete /></ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete "{documentToDelete?.filename}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DocumentTable;