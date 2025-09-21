import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Paper,
  Typography,
  Container,
  Fade,
} from '@mui/material';
import { Send, AutoAwesome } from '@mui/icons-material';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import QuerySuggestions from './QuerySuggestions';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: DocumentSource[];
  confidence?: number;
  followUpQuestions?: string[];
}

interface DocumentSource {
  documentId: string;
  filename: string;
  relevanceScore: number;
  excerpt: string;
}

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestedQueries = [
    "What are the side effects of metformin?",
    "Explain the treatment protocol for diabetes",
    "What medications are contraindicated with warfarin?",
    "Describe the symptoms of hypertension"
  ];

  useEffect(() => {
    setSessionId(generateSessionId());
    
    const welcomeMessage: ChatMessage = {
      id: 'welcome',
      type: 'assistant',
      content: 'Hello! I\'m EchoMind, your medical document assistant. I can help you find information from your uploaded medical documents. What would you like to know?',
      timestamp: new Date(),
      followUpQuestions: suggestedQueries.slice(0, 2)
    };
    setMessages([welcomeMessage]);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const generateSessionId = (): string => {
    return 'session_' + Math.random().toString(36).substr(2, 9);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (query: string) => {
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    
    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      type: 'user',
      content: query,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');

    try {
      const response = await fetch('http://localhost:8000/api/chat/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          sessionId,
          history: messages.slice(-5)
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();
      
      const assistantMessage: ChatMessage = {
        id: `assistant_${Date.now()}`,
        type: 'assistant',
        content: data.response.answer,
        timestamp: new Date(),
        sources: data.response.sources,
        confidence: data.response.confidence,
        followUpQuestions: data.response.followUpQuestions
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      
    } catch (error) {
      console.error('Chat error:', error);
      
      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        type: 'assistant',
        content: 'I apologize, but I encountered an error processing your request. Please try again or check if your documents have been uploaded and processed.',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage(inputValue);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion);
  };

  return (
    <Container maxWidth="md" sx={{ height: '100vh', display: 'flex', flexDirection: 'column', py: 2 }}>
      <Paper 
        elevation={1} 
        sx={{ 
          p: 2, 
          mb: 2, 
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white'
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoAwesome />
          <Typography variant="h6" fontWeight="bold">
            EchoMind Medical Assistant
          </Typography>
        </Box>
        <Typography variant="body2" sx={{ opacity: 0.9, mt: 0.5 }}>
          Ask questions about your medical documents in natural language
        </Typography>
      </Paper>

      <Paper 
        elevation={1} 
        sx={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          overflow: 'hidden',
          mb: 2
        }}
      >
        <Box 
          sx={{ 
            flex: 1, 
            overflowY: 'auto', 
            p: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 2
          }}
        >
          {messages.map((message) => (
            <Fade in={true} key={message.id}>
              <div>
                <MessageBubble message={message} />
              </div>
            </Fade>
          ))}
          
          {isLoading && <TypingIndicator />}
          
          {(messages.length <= 1 || (messages[messages.length - 1]?.type === 'assistant' && !isLoading)) && (
            <QuerySuggestions 
              suggestions={
                messages[messages.length - 1]?.followUpQuestions || suggestedQueries
              }
              onSuggestionClick={handleSuggestionClick}
            />
          )}
          
          <div ref={messagesEndRef} />
        </Box>
      </Paper>

      <Paper elevation={2} sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <TextField
            fullWidth
            multiline
            maxRows={4}
            placeholder="Ask about your medical documents..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 3,
              }
            }}
          />
          <IconButton
            onClick={() => sendMessage(inputValue)}
            disabled={!inputValue.trim() || isLoading}
            sx={{
              bgcolor: 'primary.main',
              color: 'white',
              '&:hover': {
                bgcolor: 'primary.dark',
              },
              '&:disabled': {
                bgcolor: 'grey.300',
              }
            }}
          >
            <Send />
          </IconButton>
        </Box>
        
        <Typography 
          variant="caption" 
          color="text.secondary" 
          sx={{ display: 'block', mt: 1, textAlign: 'center' }}
        >
          Press Enter to send, Shift+Enter for new line
        </Typography>
      </Paper>
    </Container>
  );
};

export default ChatInterface;