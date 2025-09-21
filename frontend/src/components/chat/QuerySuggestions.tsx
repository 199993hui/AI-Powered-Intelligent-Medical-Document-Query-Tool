import React from 'react';
import {
  Box,
  Chip,
  Typography,
  Paper,
  Fade,
} from '@mui/material';
import { LightbulbOutlined } from '@mui/icons-material';

interface QuerySuggestionsProps {
  suggestions: string[];
  onSuggestionClick: (suggestion: string) => void;
}

const QuerySuggestions: React.FC<QuerySuggestionsProps> = ({
  suggestions,
  onSuggestionClick,
}) => {
  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  return (
    <Fade in={true}>
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          bgcolor: 'background.paper',
          borderStyle: 'dashed',
          borderColor: 'primary.main',
          borderWidth: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <LightbulbOutlined color="primary" fontSize="small" />
          <Typography variant="body2" color="primary" fontWeight="medium">
            Suggested questions
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {suggestions.slice(0, 4).map((suggestion, index) => (
            <Chip
              key={index}
              label={suggestion}
              variant="outlined"
              clickable
              onClick={() => onSuggestionClick(suggestion)}
              sx={{
                height: 'auto',
                py: 1,
                px: 1.5,
                fontSize: '0.875rem',
                borderColor: 'primary.main',
                color: 'primary.main',
                '& .MuiChip-label': {
                  whiteSpace: 'normal',
                  textAlign: 'left',
                  lineHeight: 1.3,
                },
                '&:hover': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  transform: 'translateY(-1px)',
                  boxShadow: 2,
                },
                transition: 'all 0.2s ease-in-out',
              }}
            />
          ))}
        </Box>
        
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1, fontStyle: 'italic' }}
        >
          Click on any suggestion to ask EchoMind
        </Typography>
      </Paper>
    </Fade>
  );
};

export default QuerySuggestions;