import React from 'react';
import { AppBar, Toolbar, Typography, Box } from '@mui/material';
import { LocalHospital } from '@mui/icons-material';

const Header: React.FC = () => {
  return (
    <AppBar 
      position="static" 
      sx={{ 
        background: 'linear-gradient(135deg, #273b96ff 0%, #764ba2 100%)',
        boxShadow: '0 4px 20px rgba(0,0,0,0.1)'
      }}
    >
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <LocalHospital sx={{ fontSize: 32, color: 'white' }} />
          <Typography 
            variant="h5" 
            component="h1" 
            sx={{ 
              fontWeight: 600,
              color: 'white',
              letterSpacing: '0.5px'
            }}
          >
            AI Medical Document Query Tool
          </Typography>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;