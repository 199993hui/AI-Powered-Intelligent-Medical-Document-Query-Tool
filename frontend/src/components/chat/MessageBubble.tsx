import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Avatar,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
} from '@mui/material';
import {
  Person,
  AutoAwesome,
  ExpandMore,
  Description,
  TrendingUp,
} from '@mui/icons-material';

interface DocumentSource {
  documentId: string;
  filename: string;
  relevanceScore: number;
  excerpt: string;
}

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: DocumentSource[];
  confidence?: number;
  followUpQuestions?: string[];
}

interface MessageBubbleProps {
  message: ChatMessage;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isAssistant = message.type === 'assistant';

  const formatTime = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'error';
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: isUser ? 'row-reverse' : 'row',
          alignItems: 'flex-start',
          gap: 1,
          maxWidth: '80%',
        }}
      >
        {/* Avatar */}
        <Avatar
          sx={{
            bgcolor: isUser ? 'primary.main' : 'secondary.main',
            width: 32,
            height: 32,
          }}
        >
          {isUser ? <Person fontSize="small" /> : <AutoAwesome fontSize="small" />}
        </Avatar>

        {/* Message Content */}
        <Paper
          elevation={1}
          sx={{
            p: 2,
            bgcolor: isUser ? 'primary.main' : 'grey.50',
            color: isUser ? 'white' : 'text.primary',
            borderRadius: 2,
            borderTopLeftRadius: isUser ? 2 : 0.5,
            borderTopRightRadius: isUser ? 0.5 : 2,
          }}
        >
          {/* Message Text */}
          <Typography
            variant="body1"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {message.content}
          </Typography>

          {/* Confidence Score for Assistant */}
          {isAssistant && message.confidence !== undefined && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingUp fontSize="small" color="action" />
              <Typography variant="caption" color="text.secondary">
                Confidence: {Math.round(message.confidence * 100)}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={message.confidence * 100}
                color={getConfidenceColor(message.confidence)}
                sx={{ flex: 1, height: 4, borderRadius: 2 }}
              />
            </Box>
          )}

          {/* Sources */}
          {isAssistant && message.sources && message.sources.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Accordion elevation={0} sx={{ bgcolor: 'transparent' }}>
                <AccordionSummary
                  expandIcon={<ExpandMore />}
                  sx={{ px: 0, minHeight: 'auto' }}
                >
                  <Typography variant="caption" color="text.secondary">
                    Sources ({message.sources.length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ px: 0, pt: 0 }}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {message.sources.map((source, index) => (
                      <Paper
                        key={index}
                        variant="outlined"
                        sx={{ p: 1.5, bgcolor: 'background.paper' }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <Description fontSize="small" color="primary" />
                          <Typography variant="body2" fontWeight="medium">
                            {source.filename}
                          </Typography>
                          <Chip
                            label={`${Math.round(source.relevanceScore * 100)}% match`}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                        </Box>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{
                            display: 'block',
                            fontStyle: 'italic',
                            bgcolor: 'grey.50',
                            p: 1,
                            borderRadius: 1,
                            border: '1px solid',
                            borderColor: 'grey.200',
                          }}
                        >
                          "{source.excerpt}"
                        </Typography>
                      </Paper>
                    ))}
                  </Box>
                </AccordionDetails>
              </Accordion>
            </Box>
          )}



          {/* Timestamp */}
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              textAlign: 'right',
              mt: 1,
              opacity: 0.7,
            }}
          >
            {formatTime(message.timestamp)}
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
};

export default MessageBubble;