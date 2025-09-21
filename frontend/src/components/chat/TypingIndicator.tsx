import React from 'react';
import {
  Box,
  Paper,
  Avatar,
  Typography,
} from '@mui/material';
import { AutoAwesome } from '@mui/icons-material';

const TypingIndicator: React.FC = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-start',
        mb: 2,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1,
          maxWidth: '80%',
        }}
      >
        {/* Avatar */}
        <Avatar
          sx={{
            bgcolor: 'secondary.main',
            width: 32,
            height: 32,
          }}
        >
          <AutoAwesome fontSize="small" />
        </Avatar>

        {/* Typing Animation */}
        <Paper
          elevation={1}
          sx={{
            p: 2,
            bgcolor: 'grey.50',
            borderRadius: 2,
            borderTopLeftRadius: 0.5,
            minWidth: 80,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              EchoMind is thinking
            </Typography>
            
            {/* Animated dots */}
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              {[0, 1, 2].map((index) => (
                <Box
                  key={index}
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    bgcolor: 'primary.main',
                    animation: 'pulse 1.4s ease-in-out infinite both',
                    animationDelay: `${index * 0.16}s`,
                    '@keyframes pulse': {
                      '0%': {
                        transform: 'scale(0)',
                        opacity: 1,
                      },
                      '100%': {
                        transform: 'scale(1)',
                        opacity: 0,
                      },
                    },
                  }}
                />
              ))}
            </Box>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default TypingIndicator;