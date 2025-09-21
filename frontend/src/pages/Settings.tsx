import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
} from '@mui/material';
import Header from '../components/Header';

const Settings: React.FC = () => {
  return (
    <Box>
      <Header />
      <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        Settings
      </Typography>

      <Card>
        <CardContent>
          <Typography variant="body1" color="text.secondary">
            Settings page coming soon...
          </Typography>
        </CardContent>
      </Card>
      </Box>
    </Box>
  );
};

export default Settings;