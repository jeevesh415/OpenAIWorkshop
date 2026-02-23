import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Box,
  ThemeProvider,
  createTheme,
  CssBaseline,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Paper,
  Grid,
  Chip,
} from '@mui/material';
import SecurityIcon from '@mui/icons-material/Security';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
import WorkflowVisualizer from './components/WorkflowVisualizer';
import EventFeed from './components/EventFeed';
import { API_CONFIG } from './constants/config';
import ControlPanel from './components/ControlPanel';
import AnalystDecisionPanel from './components/AnalystDecisionPanel';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    success: {
      main: '#4caf50',
    },
    warning: {
      main: '#ff9800',
    },
    error: {
      main: '#f44336',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
});

function App() {
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [workflowRunning, setWorkflowRunning] = useState(false);
  const [events, setEvents] = useState([]);
  const [pendingDecision, setPendingDecision] = useState(null);
  const [executorStates, setExecutorStates] = useState({});
  const [instanceId, setInstanceId] = useState(null);
  const [orchestrationStatus, setOrchestrationStatus] = useState(null);
  const [stepDetails, setStepDetails] = useState({});
  
  const ws = useRef(null);

  // Load sample alerts on mount
  useEffect(() => {
    fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.ALERTS}`)
      .then((res) => res.json())
      .then((data) => setAlerts(data))
      .catch((err) => console.error('Error loading alerts:', err));
  }, []);

  const addEvent = useCallback((event) => {
    setEvents((prev) => [...prev, { ...event, timestamp: event.timestamp || new Date().toISOString() }]);
  }, []);

  // Connect to WebSocket when we have an instance ID
  useEffect(() => {
    if (!instanceId) return;

    const wsUrl = `${API_CONFIG.WS_URL}/${instanceId}`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connected for instance:', instanceId);
      addEvent({ type: 'websocket_connected', message: `Connected to orchestration ${instanceId}` });
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message:', data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [instanceId]);

  const handleWebSocketMessage = useCallback((data) => {
    // Skip ping/pong messages
    if (data.type === 'ping' || data.type === 'pong') return;

    // Add to event log
    addEvent(data);

    // Handle different message types
    if (data.type === 'status_update' || data.type === 'initial_status') {
      setOrchestrationStatus(data.status);
      
      // Update step details from backend (real tool calls and outputs)
      if (data.step_details) {
        setStepDetails(data.step_details);
      }
      
      // Map orchestration status to executor states based on custom_status
      const customStatus = data.custom_status || '';
      
      if (customStatus.includes('Running fraud analysis')) {
        // Workflow is running - show specialist agents as active
        setExecutorStates({
          alert_router: 'completed',
          usage_pattern_executor: 'running',
          location_analysis_executor: 'running',
          billing_charge_executor: 'running',
        });
        setPendingDecision(null);
      } else if (customStatus.includes('Re-investigating')) {
        // Re-investigation after analyst rejection - reset analysis nodes
        setExecutorStates({
          alert_router: 'completed',
          usage_pattern_executor: 'running',
          location_analysis_executor: 'running',
          billing_charge_executor: 'running',
          fraud_risk_aggregator: 'idle',
          review_gateway: 'idle',
        });
        setPendingDecision(null);
        setWorkflowRunning(true);
      } else if (customStatus.includes('Awaiting analyst')) {
        // Waiting for analyst - aggregation complete, waiting for human
        setExecutorStates({
          alert_router: 'completed',
          usage_pattern_executor: 'completed',
          location_analysis_executor: 'completed',
          billing_charge_executor: 'completed',
          fraud_risk_aggregator: 'completed',
          review_gateway: 'running',
        });
      } else if (customStatus.includes('Executing')) {
        // Executing analyst-approved action
        setExecutorStates((prev) => ({
          ...prev,
          review_gateway: 'completed',
          fraud_action_executor: 'running',
        }));
      } else if (customStatus.includes('Auto-clearing')) {
        // Auto-clearing low risk
        setExecutorStates({
          alert_router: 'completed',
          usage_pattern_executor: 'completed',
          location_analysis_executor: 'completed',
          billing_charge_executor: 'completed',
          fraud_risk_aggregator: 'completed',
          auto_clear_executor: 'running',
        });
      } else if (customStatus.includes('Sending notification') || customStatus.includes('Sending')) {
        // Sending final notification
        setExecutorStates((prev) => ({
          ...prev,
          fraud_action_executor: prev.fraud_action_executor === 'running' ? 'completed' : prev.fraud_action_executor,
          auto_clear_executor: prev.auto_clear_executor === 'running' ? 'completed' : prev.auto_clear_executor,
          final_notification_executor: 'running',
        }));
      } else if (customStatus.includes('Completed') || data.status === 'COMPLETED') {
        // Completed - mark everything as done
        setExecutorStates((prev) => ({
          ...prev,
          fraud_action_executor: prev.fraud_action_executor === 'running' ? 'completed' : prev.fraud_action_executor,
          auto_clear_executor: prev.auto_clear_executor === 'running' ? 'completed' : prev.auto_clear_executor,
          final_notification_executor: 'completed',
        }));
      }

      // Check if decision is required (including re-investigation returns)
      if (data.decision_required || customStatus.includes('Awaiting analyst')) {
        setPendingDecision({
          instance_id: instanceId,
          alert_id: selectedAlert?.alert_id,
          customer_id: selectedAlert?.customer_id,
        });
        setWorkflowRunning(false);
      }

      // Check if completed
      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        setWorkflowRunning(false);
        
        // Determine which path was taken from the result
        const actionTaken = data.result?.action_taken || '';
        const riskScore = data.result?.risk_score || 0;
        
        // Update step details from result if available
        if (data.result?.step_details) {
          setStepDetails(data.result.step_details);
        }
        
        // Set the complete final state based on the path taken
        if (actionTaken === 'auto_clear' || riskScore < 0.6) {
          // Low risk path: auto-clear
          setExecutorStates({
            alert_router: 'completed',
            usage_pattern_executor: 'completed',
            location_analysis_executor: 'completed',
            billing_charge_executor: 'completed',
            fraud_risk_aggregator: 'completed',
            auto_clear_executor: 'completed',
            final_notification_executor: 'completed',
          });
        } else {
          // High risk path: review gateway → fraud action
          setExecutorStates({
            alert_router: 'completed',
            usage_pattern_executor: 'completed',
            location_analysis_executor: 'completed',
            billing_charge_executor: 'completed',
            fraud_risk_aggregator: 'completed',
            review_gateway: 'completed',
            fraud_action_executor: 'completed',
            final_notification_executor: 'completed',
          });
        }
      }

      // Handle result
      if (data.result) {
        addEvent({ type: 'workflow_result', ...data.result });
      }
    }

    if (data.type === 'decision_submitted') {
      setPendingDecision(null);
      setWorkflowRunning(true);
      // Don't assume approve — the status_update handler will set the right state
      // based on whether the orchestration goes to "Executing" or "Re-investigating"
    }
  }, [instanceId, selectedAlert, addEvent]);

  const handleStartWorkflow = useCallback(async (alert) => {
    console.log('Starting workflow for alert:', alert);
    setSelectedAlert(alert);
    setWorkflowRunning(true);
    setEvents([]);
    setExecutorStates({ alert_router: 'running' });
    setPendingDecision(null);
    setInstanceId(null);
    setOrchestrationStatus(null);
    setStepDetails({});  // Reset step details for new workflow

    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.WORKFLOW_START}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          alert_id: alert.alert_id,
          customer_id: alert.customer_id,
          alert_type: alert.alert_type,
          description: alert.description,
          severity: alert.severity,
          approval_timeout_hours: 0.05, // 3 minutes for demo
        }),
      });

      const data = await response.json();
      console.log('Workflow started:', data);
      
      // Store instance ID - this triggers WebSocket connection
      setInstanceId(data.instance_id);
      addEvent({ type: 'workflow_started', instance_id: data.instance_id, alert_id: alert.alert_id });
      
    } catch (error) {
      console.error('Error starting workflow:', error);
      setWorkflowRunning(false);
      addEvent({ type: 'error', message: error.message });
    }
  }, [addEvent]);

  const handleSubmitDecision = useCallback(async (decision) => {
    console.log('Submitting decision:', decision);

    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.WORKFLOW_DECISION}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          instance_id: instanceId,
          alert_id: selectedAlert?.alert_id,
          approved: decision.approved !== false,
          approved_action: decision.approved_action || 'clear',
          feedback: decision.feedback || '',
          analyst_notes: decision.analyst_notes || '',
          analyst_id: 'analyst_ui',
        }),
      });

      const data = await response.json();
      console.log('Decision submitted:', data);
      addEvent({ type: 'decision_submitted', action: decision.approved_action });

    } catch (error) {
      console.error('Error submitting decision:', error);
      addEvent({ type: 'error', message: error.message });
    }
  }, [instanceId, selectedAlert, addEvent]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        {/* App Bar */}
        <AppBar position="static" elevation={2}>
          <Toolbar>
            <SecurityIcon sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Durable Fraud Detection Workflow
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {instanceId && (
                <Chip
                  icon={<CloudSyncIcon />}
                  label={`Instance: ${instanceId.substring(0, 20)}...`}
                  color={orchestrationStatus === 'RUNNING' ? 'primary' : orchestrationStatus === 'COMPLETED' ? 'success' : 'default'}
                  size="small"
                />
              )}
              <Typography variant="body2" sx={{ opacity: 0.8 }}>
                Hybrid Workflow + Durable Task
              </Typography>
            </Box>
          </Toolbar>
        </AppBar>

        {/* Main Content */}
        <Container maxWidth={false} sx={{ flex: 1, py: 3, overflow: 'hidden' }}>
          <Grid container spacing={2} sx={{ height: '100%' }}>
            {/* Left Column - Controls, Decision Panel, and Live Feed */}
            <Grid size={{ xs: 12, md: 3 }} sx={{ display: 'flex', flexDirection: 'column', gap: 2, height: '100%', minHeight: 0 }}>
              <ControlPanel
                alerts={alerts}
                onStartWorkflow={handleStartWorkflow}
                workflowRunning={workflowRunning}
                selectedAlert={selectedAlert}
              />

              {pendingDecision && (
                <AnalystDecisionPanel
                  decision={pendingDecision}
                  onSubmit={handleSubmitDecision}
                />
              )}

              {/* Layer 1 Live Feed */}
              <Box sx={{ flex: 1, minHeight: 200 }}>
                <EventFeed
                  onWorkflowAutoStarted={(alertData) => {
                    // Connect the auto-triggered workflow to the visualizer
                    const syntheticAlert = {
                      alert_id: alertData.alert_id,
                      customer_id: alertData.customer_id,
                      alert_type: alertData.alert_type,
                      description: alertData.description,
                      severity: alertData.severity,
                      auto_detected: true,
                    };
                    setSelectedAlert(syntheticAlert);
                    setWorkflowRunning(true);
                    setEvents([]);
                    setExecutorStates({ alert_router: 'running' });
                    setPendingDecision(null);
                    setStepDetails({});
                    // Setting instanceId triggers the WebSocket connection
                    setInstanceId(alertData.instance_id);
                    addEvent({
                      type: 'workflow_auto_started',
                      instance_id: alertData.instance_id,
                      alert_id: alertData.alert_id,
                      message: `Layer 1 auto-detected ${alertData.alert_type} — investigation started`,
                    });
                  }}
                />
              </Box>
            </Grid>

            {/* Center Column - Workflow Visualization */}
            <Grid size={{ xs: 12, md: 9 }} sx={{ height: '100%' }}>
              <Paper elevation={3} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="h6">Workflow Graph</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedAlert
                      ? `Alert: ${selectedAlert.alert_id} - ${selectedAlert.description}`
                      : 'Select an alert to start'}
                    {orchestrationStatus && ` | Status: ${orchestrationStatus}`}
                  </Typography>
                </Box>
                <Box sx={{ flex: 1, minHeight: 400, position: 'relative' }}>
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
                    <WorkflowVisualizer executorStates={executorStates} stepDetails={stepDetails} />
                  </div>
                </Box>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
