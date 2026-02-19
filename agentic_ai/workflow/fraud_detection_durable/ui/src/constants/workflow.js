/**
 * Workflow event types
 */
export const EVENT_TYPES = {
  WORKFLOW_INITIALIZING: 'workflow_initializing',
  WORKFLOW_STARTED: 'workflow_started',
  WORKFLOW_COMPLETED: 'workflow_completed',
  WORKFLOW_ERROR: 'workflow_error',
  EXECUTOR_INVOKED: 'executor_invoked',
  EXECUTOR_COMPLETED: 'executor_completed',
  DECISION_REQUIRED: 'decision_required',
  STATUS_CHANGE: 'status_change',
  WORKFLOW_OUTPUT: 'workflow_output',
};

/**
 * Alert severity levels
 */
export const SEVERITY_LEVELS = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
};

/**
 * Executor states
 */
export const EXECUTOR_STATES = {
  IDLE: 'idle',
  RUNNING: 'running',
  COMPLETED: 'completed',
  ERROR: 'error',
};

/**
 * Fraud action options
 */
export const ACTION_OPTIONS = [
  { value: 'clear', label: 'Clear - No Action Needed', color: 'success' },
  { value: 'lock_account', label: 'Lock Account', color: 'error' },
  { value: 'refund_charges', label: 'Refund Charges', color: 'warning' },
  { value: 'both', label: 'Lock Account & Refund', color: 'error' },
];

/**
 * Decision modes
 */
export const DECISION_MODES = [
  { value: 'approve', label: 'Approve Action', color: 'success' },
  { value: 'reject', label: 'Reject & Request Re-investigation', color: 'error' },
];

/**
 * WebSocket ready states
 */
export const WS_READY_STATES = {
  CONNECTING: 'CONNECTING',
  OPEN: 'OPEN',
  CLOSING: 'CLOSING',
  CLOSED: 'CLOSED',
};
