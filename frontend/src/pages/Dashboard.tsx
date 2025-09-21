import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
} from '@mui/material';
import {
  FolderOpen,
  Search,
  TrendingUp,
  Description,
} from '@mui/icons-material';
import Header from '../components/Header';

const Dashboard: React.FC = () => {
  return (
    <Box>
      <Header />
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
          Dashboard
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          <Box sx={{ flex: '1 1 250px', minWidth: 250 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Description sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6">Total Documents</Typography>
                </Box>
                <Typography variant="h4" color="primary">
                  0
                </Typography>
              </CardContent>
            </Card>
          </Box>

          <Box sx={{ flex: '1 1 250px', minWidth: 250 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <FolderOpen sx={{ mr: 1, color: 'success.main' }} />
                  <Typography variant="h6">Processed</Typography>
                </Box>
                <Typography variant="h4" color="success.main">
                  0
                </Typography>
              </CardContent>
            </Card>
          </Box>

          <Box sx={{ flex: '1 1 250px', minWidth: 250 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Search sx={{ mr: 1, color: 'info.main' }} />
                  <Typography variant="h6">Searches Today</Typography>
                </Box>
                <Typography variant="h4" color="info.main">
                  0
                </Typography>
              </CardContent>
            </Card>
          </Box>

          <Box sx={{ flex: '1 1 250px', minWidth: 250 }}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <TrendingUp sx={{ mr: 1, color: 'warning.main' }} />
                  <Typography variant="h6">Accuracy</Typography>
                </Box>
                <Typography variant="h4" color="warning.main">
                  95%
                </Typography>
              </CardContent>
            </Card>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;