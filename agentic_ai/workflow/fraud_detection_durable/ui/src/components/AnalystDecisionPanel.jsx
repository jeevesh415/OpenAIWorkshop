import { useState } from 'react';
import {
  Paper,
  Box,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Alert,
  Divider,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import GavelIcon from '@mui/icons-material/Gavel';
import SendIcon from '@mui/icons-material/Send';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { ACTION_OPTIONS } from '../constants/workflow';

/**
 * Panel for analyst to approve or reject (with feedback) fraud alerts.
 * Supports the stateful HITL feedback loop.
 */
function AnalystDecisionPanel({ decision, onSubmit }) {
  const [mode, setMode] = useState('approve'); // 'approve' or 'reject'
  const [selectedAction, setSelectedAction] = useState(
    decision.recommended_action || 'lock_account'
  );
  const [notes, setNotes] = useState('');
  const [feedback, setFeedback] = useState('');

  const handleSubmit = () => {
    if (mode === 'approve') {
      onSubmit({
        instance_id: decision.instance_id,
        alert_id: decision.alert_id,
        customer_id: decision.customer_id,
        approved: true,
        approved_action: selectedAction,
        analyst_notes: notes || 'Approved from UI',
        analyst_id: 'analyst_ui',
      });
    } else {
      onSubmit({
        instance_id: decision.instance_id,
        alert_id: decision.alert_id,
        customer_id: decision.customer_id,
        approved: false,
        approved_action: '',
        feedback: feedback || 'Please investigate further',
        analyst_notes: notes,
        analyst_id: 'analyst_ui',
      });
    }
  };

  return (
    <Paper
      elevation={3}
      sx={{
        p: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        border: 2,
        borderColor: 'warning.main',
        animation: 'pulse 2s ease-in-out infinite',
        maxHeight: '50vh',
        overflow: 'auto',
        '@keyframes pulse': {
          '0%, 100%': { borderColor: '#ff9800' },
          '50%': { borderColor: '#ffc107' },
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <GavelIcon color="warning" fontSize="small" />
        <Typography variant="subtitle1" fontWeight="bold">Analyst Review Required</Typography>
      </Box>

      <Alert severity="warning" sx={{ py: 0.25, px: 1 }}>
        <Typography variant="caption" fontWeight="bold">
          Human Decision Needed
        </Typography>
      </Alert>

      <Divider sx={{ my: 0.5 }} />

      {/* Risk Assessment */}
      <Box>
        <Typography variant="caption" fontWeight="bold" display="block" sx={{ mb: 0.5 }}>
          Review Required
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', mb: 0.5 }}>
          <Typography variant="caption">Alert ID:</Typography>
          <Chip label={decision.alert_id || 'N/A'} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.7rem' }} />
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
          <Typography variant="caption">Customer:</Typography>
          <Chip label={decision.customer_id || 'N/A'} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.7rem' }} />
        </Box>
      </Box>

      {/* Instance Info */}
      <Box>
        <Typography variant="caption" fontWeight="bold" display="block" sx={{ mb: 0.5 }}>
          Instance ID
        </Typography>
        <Typography variant="caption" sx={{ wordBreak: 'break-all', fontSize: '0.65rem', opacity: 0.7 }}>
          {decision.instance_id}
        </Typography>
      </Box>

      <Divider sx={{ my: 0.5 }} />

      {/* Approve / Reject Toggle */}
      <ToggleButtonGroup
        value={mode}
        exclusive
        onChange={(e, val) => val && setMode(val)}
        fullWidth
        size="small"
        sx={{ mb: 0.5 }}
      >
        <ToggleButton value="approve" color="success" sx={{ fontSize: '0.75rem', py: 0.5 }}>
          <CheckCircleIcon fontSize="small" sx={{ mr: 0.5 }} />
          Approve
        </ToggleButton>
        <ToggleButton value="reject" color="error" sx={{ fontSize: '0.75rem', py: 0.5 }}>
          <CancelIcon fontSize="small" sx={{ mr: 0.5 }} />
          Reject
        </ToggleButton>
      </ToggleButtonGroup>

      {/* Approve: Action selector */}
      {mode === 'approve' && (
        <FormControl fullWidth size="small" sx={{ minHeight: 40 }}>
          <InputLabel sx={{ fontSize: '0.875rem' }}>Action to Execute</InputLabel>
          <Select
            value={selectedAction}
            label="Action to Execute"
            onChange={(e) => setSelectedAction(e.target.value)}
            sx={{ fontSize: '0.875rem' }}
          >
            {ACTION_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value} sx={{ fontSize: '0.875rem' }}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {/* Reject: Feedback field */}
      {mode === 'reject' && (
        <>
          <Alert severity="info" sx={{ py: 0.25, px: 1 }}>
            <Typography variant="caption">
              Provide feedback for the AI to re-investigate with more context.
            </Typography>
          </Alert>
          <TextField
            label="Feedback for Re-investigation"
            multiline
            rows={3}
            fullWidth
            size="small"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="e.g. Check billing charges in the last 7 days more carefully..."
            sx={{ '& .MuiInputBase-input': { fontSize: '0.875rem' } }}
            required
          />
        </>
      )}

      <TextField
        label="Analyst Notes (optional)"
        multiline
        rows={1}
        fullWidth
        size="small"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Add notes..."
        sx={{ '& .MuiInputBase-input': { fontSize: '0.875rem' } }}
      />

      <Button
        variant="contained"
        color={mode === 'approve' ? 'success' : 'error'}
        size="small"
        fullWidth
        startIcon={mode === 'approve' ? <CheckCircleIcon fontSize="small" /> : <CancelIcon fontSize="small" />}
        onClick={handleSubmit}
        disabled={mode === 'reject' && !feedback.trim()}
        sx={{ mt: 0.5, py: 0.75 }}
      >
        {mode === 'approve' ? 'Approve & Execute' : 'Reject & Re-investigate'}
      </Button>
    </Paper>
  );
}

export default AnalystDecisionPanel;
