/**
 * WebSocket Client Examples for PD Prime Demo
 *
 * These examples show how to integrate with the WebSocket API
 * for real-time quotes, analytics, and notifications.
 */

/**
 * WebSocket Client Class
 * Handles connection, reconnection, and message routing
 */
class PDPrimeWebSocketClient {
    constructor(url, token = null) {
        this.url = url;
        this.token = token;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.messageSequence = 0;
        this.messageHandlers = new Map();
        this.connectionPromise = null;

        // Message acknowledgment tracking
        this.pendingAcks = new Map();
        this.ackTimeout = 5000; // 5 seconds
    }

    /**
     * Connect to WebSocket server
     */
    async connect() {
        if (this.connectionPromise) {
            return this.connectionPromise;
        }

        this.connectionPromise = new Promise((resolve, reject) => {
            try {
                const wsUrl = new URL(this.url);
                if (this.token) {
                    wsUrl.searchParams.append('token', this.token);
                }

                this.ws = new WebSocket(wsUrl.toString());

                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    this.reconnectDelay = 1000;
                    this._setupHeartbeat();
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    this._handleMessage(JSON.parse(event.data));
                };

                this.ws.onclose = (event) => {
                    console.log('WebSocket disconnected:', event.code, event.reason);
                    this.connectionPromise = null;
                    this._cleanup();

                    if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                        this._scheduleReconnect();
                    }
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(error);
                };

            } catch (error) {
                reject(error);
            }
        });

        return this.connectionPromise;
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
        }
        this._cleanup();
    }

    /**
     * Subscribe to message type
     */
    on(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        this.messageHandlers.get(messageType).push(handler);
    }

    /**
     * Unsubscribe from message type
     */
    off(messageType, handler) {
        if (this.messageHandlers.has(messageType)) {
            const handlers = this.messageHandlers.get(messageType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Send message with automatic retry and acknowledgment
     */
    async send(message, requireAck = false) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            await this.connect();
        }

        const messageWithSeq = {
            ...message,
            sequence: ++this.messageSequence,
            timestamp: new Date().toISOString()
        };

        this.ws.send(JSON.stringify(messageWithSeq));

        if (requireAck) {
            return this._waitForAck(messageWithSeq.sequence);
        }
    }

    /**
     * Subscribe to quote updates
     */
    async subscribeToQuote(quoteId) {
        await this.send({
            type: 'quote_subscribe',
            quote_id: quoteId
        });
    }

    /**
     * Unsubscribe from quote updates
     */
    async unsubscribeFromQuote(quoteId) {
        await this.send({
            type: 'quote_unsubscribe',
            quote_id: quoteId
        });
    }

    /**
     * Edit quote field collaboratively
     */
    async editQuoteField(quoteId, field, value) {
        await this.send({
            type: 'quote_edit',
            data: {
                quote_id: quoteId,
                field: field,
                value: value
            }
        });
    }

    /**
     * Indicate field focus for collaborative editing
     */
    async setFieldFocus(quoteId, field, focused) {
        await this.send({
            type: 'field_focus',
            quote_id: quoteId,
            field: field,
            focused: focused
        });
    }

    /**
     * Update cursor position for collaborative editing
     */
    async updateCursorPosition(quoteId, field, position) {
        await this.send({
            type: 'cursor_position',
            quote_id: quoteId,
            field: field,
            position: position
        });
    }

    /**
     * Start analytics dashboard
     */
    async startAnalytics(dashboardType, options = {}) {
        await this.send({
            type: 'start_analytics',
            dashboard_type: dashboardType,
            update_interval: options.updateInterval || 5,
            filters: options.filters || {},
            metrics: options.metrics || [],
            time_range_hours: options.timeRangeHours || 24
        });
    }

    /**
     * Stop analytics dashboard
     */
    async stopAnalytics(dashboardType) {
        await this.send({
            type: 'stop_analytics',
            dashboard_type: dashboardType
        });
    }

    /**
     * Acknowledge notification
     */
    async acknowledgeNotification(notificationId) {
        await this.send({
            type: 'notification_acknowledge',
            notification_id: notificationId
        }, true);
    }

    // Private methods

    _handleMessage(message) {
        console.log('Received message:', message);

        // Handle acknowledgments
        if (message.type === 'ack' && message.sequence) {
            this._handleAck(message.sequence);
        }

        // Route to handlers
        if (this.messageHandlers.has(message.type)) {
            const handlers = this.messageHandlers.get(message.type);
            handlers.forEach(handler => {
                try {
                    handler(message);
                } catch (error) {
                    console.error('Error in message handler:', error);
                }
            });
        }

        // Handle connection lifecycle messages
        if (message.type === 'connection') {
            console.log('Connection established:', message.data);
        } else if (message.type === 'error') {
            console.error('Server error:', message.data);
        }
    }

    _setupHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({
                    type: 'ping',
                    timestamp: new Date().toISOString()
                });
            }
        }, 30000); // 30 seconds
    }

    _scheduleReconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect().catch(error => {
                console.error('Reconnection failed:', error);
            });
        }, delay);
    }

    _cleanup() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }

        // Clear pending acknowledgments
        this.pendingAcks.forEach(({ reject }) => {
            reject(new Error('Connection closed'));
        });
        this.pendingAcks.clear();
    }

    _waitForAck(sequence) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pendingAcks.delete(sequence);
                reject(new Error('Acknowledgment timeout'));
            }, this.ackTimeout);

            this.pendingAcks.set(sequence, { resolve, reject, timeout });
        });
    }

    _handleAck(sequence) {
        if (this.pendingAcks.has(sequence)) {
            const { resolve, timeout } = this.pendingAcks.get(sequence);
            clearTimeout(timeout);
            this.pendingAcks.delete(sequence);
            resolve();
        }
    }
}

/**
 * Quote Collaboration Manager
 * Handles collaborative quote editing features
 */
class QuoteCollaborationManager {
    constructor(client, quoteId) {
        this.client = client;
        this.quoteId = quoteId;
        this.activeEditors = new Map();
        this.fieldLocks = new Map();
        this.cursors = new Map();

        this._setupEventHandlers();
    }

    async initialize() {
        await this.client.subscribeToQuote(this.quoteId);
    }

    async cleanup() {
        await this.client.unsubscribeFromQuote(this.quoteId);
    }

    // Field editing
    async editField(fieldName, value) {
        await this.client.editQuoteField(this.quoteId, fieldName, value);
    }

    async focusField(fieldName) {
        await this.client.setFieldFocus(this.quoteId, fieldName, true);
    }

    async blurField(fieldName) {
        await this.client.setFieldFocus(this.quoteId, fieldName, false);
    }

    async updateCursor(fieldName, position) {
        await this.client.updateCursorPosition(this.quoteId, fieldName, position);
    }

    // Event callbacks (override these)
    onQuoteUpdate(update) {
        console.log('Quote updated:', update);
    }

    onEditorJoined(editor) {
        console.log('Editor joined:', editor);
        this.activeEditors.set(editor.connection_id, editor);
    }

    onEditorLeft(editor) {
        console.log('Editor left:', editor);
        this.activeEditors.delete(editor.connection_id);
    }

    onFieldLocked(lock) {
        console.log('Field locked:', lock);
        this.fieldLocks.set(lock.field, lock);
    }

    onFieldUnlocked(unlock) {
        console.log('Field unlocked:', unlock);
        this.fieldLocks.delete(unlock.field);
    }

    onCursorMoved(cursor) {
        console.log('Cursor moved:', cursor);
        this.cursors.set(`${cursor.user_id}_${cursor.field}`, cursor);
    }

    onCalculationProgress(progress) {
        console.log('Calculation progress:', progress);
    }

    _setupEventHandlers() {
        this.client.on('quote_update', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onQuoteUpdate(message.data.update);
            }
        });

        this.client.on('quote_editor_joined', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onEditorJoined(message.data);
            }
        });

        this.client.on('quote_editor_left', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onEditorLeft(message.data);
            }
        });

        this.client.on('field_locked', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onFieldLocked(message.data);
            }
        });

        this.client.on('field_unlocked', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onFieldUnlocked(message.data);
            }
        });

        this.client.on('cursor_position', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onCursorMoved(message.data);
            }
        });

        this.client.on('calculation_progress', (message) => {
            if (message.data.quote_id === this.quoteId) {
                this.onCalculationProgress(message.data);
            }
        });
    }
}

/**
 * Analytics Dashboard Manager
 * Handles real-time analytics dashboard updates
 */
class AnalyticsDashboardManager {
    constructor(client, dashboardType) {
        this.client = client;
        this.dashboardType = dashboardType;
        this.isActive = false;
        this.currentData = null;

        this._setupEventHandlers();
    }

    async start(options = {}) {
        if (this.isActive) {
            return;
        }

        await this.client.startAnalytics(this.dashboardType, options);
        this.isActive = true;
    }

    async stop() {
        if (!this.isActive) {
            return;
        }

        await this.client.stopAnalytics(this.dashboardType);
        this.isActive = false;
    }

    // Event callbacks (override these)
    onDataUpdate(data) {
        console.log('Analytics data updated:', data);
        this.currentData = data;
    }

    onEvent(event) {
        console.log('Analytics event:', event);
    }

    onAlert(alert) {
        console.log('Analytics alert:', alert);
    }

    onError(error) {
        console.error('Analytics error:', error);
    }

    _setupEventHandlers() {
        this.client.on('analytics_data', (message) => {
            if (message.data.dashboard === this.dashboardType) {
                this.onDataUpdate(message.data.metrics);
            }
        });

        this.client.on('analytics_update', (message) => {
            if (message.data.dashboard === this.dashboardType) {
                this.onDataUpdate(message.data.metrics);
            }
        });

        this.client.on('analytics_event', (message) => {
            this.onEvent(message.data);
        });

        this.client.on('analytics_alert', (message) => {
            this.onAlert(message.data);
        });

        this.client.on('analytics_error', (message) => {
            if (message.data.dashboard === this.dashboardType) {
                this.onError(message.data);
            }
        });
    }
}

/**
 * Notification Manager
 * Handles real-time notifications and alerts
 */
class NotificationManager {
    constructor(client) {
        this.client = client;
        this.activeNotifications = new Map();
        this.notificationHistory = [];

        this._setupEventHandlers();
    }

    async acknowledgeNotification(notificationId) {
        await this.client.acknowledgeNotification(notificationId);

        if (this.activeNotifications.has(notificationId)) {
            const notification = this.activeNotifications.get(notificationId);
            notification.acknowledged = true;
            notification.acknowledgedAt = new Date();
        }
    }

    // Event callbacks (override these)
    onNotification(notification) {
        console.log('New notification:', notification);

        this.activeNotifications.set(notification.id, {
            ...notification,
            receivedAt: new Date(),
            acknowledged: false
        });

        this.notificationHistory.push(notification);
    }

    onSystemAlert(alert) {
        console.log('System alert:', alert);

        // Auto-acknowledge low severity alerts
        if (alert.severity === 'low' && !alert.requires_action) {
            // Could auto-dismiss after a timeout
        }
    }

    onNotificationAcknowledged(ack) {
        console.log('Notification acknowledged:', ack);

        if (this.activeNotifications.has(ack.notification_id)) {
            this.activeNotifications.delete(ack.notification_id);
        }
    }

    _setupEventHandlers() {
        this.client.on('notification', (message) => {
            this.onNotification(message.data);
        });

        this.client.on('system_alert', (message) => {
            this.onSystemAlert(message.data);
        });

        this.client.on('notification_acknowledged', (message) => {
            this.onNotificationAcknowledged(message.data);
        });

        this.client.on('alert_resolved', (message) => {
            console.log('Alert resolved:', message.data);
        });
    }
}

/**
 * Usage Examples
 */

// Example 1: Basic connection and quote collaboration
async function exampleQuoteCollaboration() {
    const client = new PDPrimeWebSocketClient('ws://localhost:8000/ws', 'demo-token');

    try {
        await client.connect();

        const quoteManager = new QuoteCollaborationManager(client, 'quote-123');

        // Override callbacks
        quoteManager.onQuoteUpdate = (update) => {
            console.log('Quote field updated:', update.field, '=', update.new_value);
            // Update UI here
        };

        quoteManager.onEditorJoined = (editor) => {
            console.log('New collaborator joined');
            // Show user avatar in UI
        };

        await quoteManager.initialize();

        // Edit a field
        await quoteManager.editField('customer_name', 'John Doe');

        // Focus on a field (for collaborative awareness)
        await quoteManager.focusField('vehicle_year');

    } catch (error) {
        console.error('Error:', error);
    }
}

// Example 2: Real-time analytics dashboard
async function exampleAnalyticsDashboard() {
    const client = new PDPrimeWebSocketClient('ws://localhost:8000/ws', 'admin-token');

    try {
        await client.connect();

        const dashboard = new AnalyticsDashboardManager(client, 'quotes');

        // Override callbacks
        dashboard.onDataUpdate = (data) => {
            console.log('Dashboard updated:', data);
            // Update charts/metrics in UI
            updateQuoteMetrics(data.summary);
            updateQuoteTimeline(data.timeline);
        };

        dashboard.onEvent = (event) => {
            console.log('Real-time event:', event);
            // Animate new data point
        };

        await dashboard.start({
            updateInterval: 5,
            timeRangeHours: 24,
            filters: { state: 'CA' }
        });

    } catch (error) {
        console.error('Error:', error);
    }
}

// Example 3: Notification handling
async function exampleNotifications() {
    const client = new PDPrimeWebSocketClient('ws://localhost:8000/ws', 'user-token');

    try {
        await client.connect();

        const notifications = new NotificationManager(client);

        // Override callbacks
        notifications.onNotification = (notification) => {
            // Show toast notification
            showToast(notification.title, notification.message, {
                priority: notification.priority,
                icon: notification.icon,
                action: notification.action_url
            });

            // Play sound if specified
            if (notification.sound) {
                playNotificationSound(notification.sound);
            }

            // Auto-acknowledge low priority notifications
            if (notification.priority === 'low' && !notification.requires_acknowledgment) {
                setTimeout(() => {
                    notifications.acknowledgeNotification(notification.id);
                }, 5000);
            }
        };

        notifications.onSystemAlert = (alert) => {
            // Show system alert banner
            showSystemAlert(alert.message, alert.severity);

            // Log for admin review
            if (alert.severity === 'critical') {
                console.error('CRITICAL ALERT:', alert);
            }
        };

    } catch (error) {
        console.error('Error:', error);
    }
}

// Helper functions (implement these in your UI framework)
function updateQuoteMetrics(summary) {
    // Update dashboard metrics
}

function updateQuoteTimeline(timeline) {
    // Update timeline chart
}

function showToast(title, message, options) {
    // Show toast notification
}

function playNotificationSound(sound) {
    // Play notification sound
}

function showSystemAlert(message, severity) {
    // Show system alert banner
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        PDPrimeWebSocketClient,
        QuoteCollaborationManager,
        AnalyticsDashboardManager,
        NotificationManager
    };
}
