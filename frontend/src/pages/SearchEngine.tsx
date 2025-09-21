import React from 'react';
import { Box } from '@mui/material';
import Header from '../components/Header';
import ChatInterface from '../components/chat/ChatInterface';

const SearchEngine: React.FC = () => {
  return (
    <Box>
      <Header />
      <ChatInterface />
    </Box>
  );
};

export default SearchEngine;