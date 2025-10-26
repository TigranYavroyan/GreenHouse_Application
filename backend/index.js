const express = require('express');
const amqp = require('amqplib');
const redis = require('redis');
const { exec, spawn } = require('child_process');
const { randomUUID } = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

class GreenhouseBackend {
    constructor() {
        this.app = express();
        this.redisClient = redis.createClient();
        this.sessions = new Map();
        this.sessionCounter = 1;
        
        // Initialize logs directory FIRST
        this.logsDir = path.join(__dirname, 'logs');
        this.ensureLogsDirectory();
        
        // Create main system logger AFTER logs directory is initialized
        this.systemLogger = this.createSystemLogger();
        
        this.setupMiddleware();
        this.setupRoutes();
        this.setupRabbitMQ();
        this.commandStats = {
            totalProcessed: 0,
            cacheHits: 0,
            cacheMisses: 0,
            errors: 0
        };
        
        this.systemLogger.info(`Backend started - Logs: ${this.logsDir}`);
    }

    ensureLogsDirectory() {
        if (!fs.existsSync(this.logsDir)) {
            fs.mkdirSync(this.logsDir, { recursive: true });
            console.log(`Created logs directory: ${this.logsDir}`);
        }
    }

    createSystemLogger() {
        const logFilePath = path.join(this.logsDir, 'backend_system.log');
        
        const logger = {
            info: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] INFO: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
                console.log(`[System] ${message}`);
            },
            
            error: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] ERROR: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
                console.error(`[System] ${message}`);
            },
            
            debug: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] DEBUG: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
            },
            
            warn: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] WARN: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
                console.warn(`[System] ${message}`);
            }
        };

        // Initialize system log file
        const header = `=== Greenhouse Backend System Log ===
Started: ${new Date().toISOString()}
Node.js: ${process.version}
Platform: ${os.platform()}/${os.arch()}
Logs Directory: ${this.logsDir}
==============================================

`;
        if (!fs.existsSync(logFilePath)) {
            fs.writeFileSync(logFilePath, header);
        } else {
            fs.appendFileSync(logFilePath, `\n\n=== Backend Restarted: ${new Date().toISOString()} ===\n\n`);
        }
        
        return logger;
    }

    createSessionLogger(sessionId) {
        const sessionNumber = this.sessionCounter++;
        const logFileName = `session_${sessionNumber}.log`;
        const logFilePath = path.join(this.logsDir, logFileName);
        
        const logger = {
            sessionId: sessionId,
            sessionNumber: sessionNumber,
            logFile: logFilePath,
            
            info: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] INFO: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
                this.systemLogger.debug(`[Session ${sessionNumber}] ${message}`);
            },
            
            error: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] ERROR: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
                this.systemLogger.error(`[Session ${sessionNumber}] ${message}`);
            },
            
            debug: (message) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] DEBUG: ${message}\n`;
                fs.appendFileSync(logFilePath, logMessage);
            },
            
            command: (commandId, action, details = '') => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] COMMAND: ${commandId} - ${action} ${details}\n`;
                fs.appendFileSync(logFilePath, logMessage);
            },
            
            getSessionInfo: () => {
                return {
                    sessionId: sessionId,
                    sessionNumber: sessionNumber,
                    logFile: logFileName,
                    created: new Date().toISOString()
                };
            }
        };

        // Initialize session log file
        const header = `=== Session Log ===
Session ID: ${sessionId}
Session Number: ${sessionNumber}
Created: ${new Date().toISOString()}
Log File: ${logFileName}
========================================

`;
        fs.writeFileSync(logFilePath, header);
        
        logger.info(`Session started - ID: ${sessionId}`);
        this.systemLogger.info(`Created new session: ${sessionId} (session_${sessionNumber}.log)`);
        
        return logger;
    }

    setupMiddleware() {
        this.app.use(express.json());
        this.app.use((req, res, next) => {
            res.header('Access-Control-Allow-Origin', '*');
            res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
            next();
        });
    }

    setupRoutes() {
        // Health check endpoint
        this.app.get('/health', (req, res) => {
            const sessionInfo = Array.from(this.sessions.entries()).map(([id, session]) => ({
                id,
                sessionNumber: session.logger.sessionNumber,
                logFile: path.basename(session.logger.logFile),
                currentPath: session.currentPath,
                createdAt: session.createdAt,
                lastActivity: session.lastActivity
            }));

            res.json({
                status: 'ok',
                timestamp: new Date().toISOString(),
                redis: this.redisClient.isOpen ? 'connected' : 'disconnected',
                rabbitmq: this.connection ? 'connected' : 'disconnected',
                sessions: sessionInfo,
                platform: os.platform(),
                logsDirectory: this.logsDir,
                totalSessions: this.sessionCounter - 1,
                stats: this.commandStats
            });
        });

        // Session management endpoints
        this.app.get('/sessions', (req, res) => {
            const sessionInfo = Array.from(this.sessions.entries()).map(([id, session]) => ({
                id,
                sessionNumber: session.logger.sessionNumber,
                logFile: path.basename(session.logger.logFile),
                currentPath: session.currentPath,
                createdAt: session.createdAt,
                lastActivity: session.lastActivity
            }));
            res.json({ sessions: sessionInfo });
        });

        // Get session log content
        this.app.get('/sessions/:sessionId/log', (req, res) => {
            const sessionId = req.params.sessionId;
            const session = this.sessions.get(sessionId);
            
            if (!session) {
                return res.status(404).json({ error: 'Session not found' });
            }

            try {
                const logContent = fs.readFileSync(session.logger.logFile, 'utf8');
                res.json({
                    sessionId: sessionId,
                    sessionNumber: session.logger.sessionNumber,
                    logFile: path.basename(session.logger.logFile),
                    content: logContent
                });
            } catch (error) {
                res.status(500).json({ error: 'Failed to read log file' });
            }
        });

        // List all log files
        this.app.get('/logs', (req, res) => {
            try {
                const files = fs.readdirSync(this.logsDir)
                    .filter(file => file.endsWith('.log'))
                    .map(file => {
                        const filePath = path.join(this.logsDir, file);
                        const stats = fs.statSync(filePath);
                        return {
                            name: file,
                            size: stats.size,
                            modified: stats.mtime,
                            path: filePath,
                            type: file.startsWith('session_') ? 'session' : 
                                  file.startsWith('frontend_') ? 'frontend' : 'system'
                        };
                    })
                    .sort((a, b) => b.modified - a.modified);
                
                res.json({ logs: files });
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        });

        // Get system log
        this.app.get('/logs/system', (req, res) => {
            try {
                const systemLogPath = path.join(this.logsDir, 'backend_system.log');
                if (fs.existsSync(systemLogPath)) {
                    const content = fs.readFileSync(systemLogPath, 'utf8');
                    res.json({
                        name: 'backend_system.log',
                        content: content
                    });
                } else {
                    res.status(404).json({ error: 'System log not found' });
                }
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        });

        this.app.delete('/sessions/:sessionId', (req, res) => {
            const sessionId = req.params.sessionId;
            if (this.sessions.has(sessionId)) {
                const session = this.sessions.get(sessionId);
                session.logger.info(`Session terminated via API`);
                this.sessions.delete(sessionId);
                this.systemLogger.info(`Session terminated: ${sessionId} (session_${session.logger.sessionNumber}.log)`);
                res.json({ 
                    message: `Session ${sessionId} deleted`,
                    logFile: path.basename(session.logger.logFile)
                });
            } else {
                res.status(404).json({ error: 'Session not found' });
            }
        });

        // Cache management endpoints
        this.app.get('/cache/keys', async (req, res) => {
            try {
                const keys = await this.redisClient.keys('cmd:*');
                res.json({ keys });
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        });

        this.app.delete('/cache/clear', async (req, res) => {
            try {
                const keys = await this.redisClient.keys('cmd:*');
                if (keys.length > 0) {
                    await this.redisClient.del(keys);
                }
                res.json({ message: `Cleared ${keys.length} cache entries` });
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        });

        // Command statistics
        this.app.get('/stats', (req, res) => {
            res.json(this.commandStats);
        });

        // Queue status endpoint
        this.app.get('/queues', async (req, res) => {
            try {
                if (!this.channel) {
                    return res.status(503).json({ error: 'RabbitMQ channel not available' });
                }
                
                const commandQueue = await this.channel.checkQueue('greenhouse_commands');
                const responseQueue = await this.channel.checkQueue('command_responses');
                
                res.json({
                    commandQueue: {
                        messageCount: commandQueue.messageCount,
                        consumerCount: commandQueue.consumerCount
                    },
                    responseQueue: {
                        messageCount: responseQueue.messageCount,
                        consumerCount: responseQueue.consumerCount
                    }
                });
            } catch (error) {
                res.status(500).json({ error: error.message });
            }
        });

        // Default route
        this.app.get('/', (req, res) => {
            res.json({
                message: 'Greenhouse Automation Backend',
                version: '1.0.0',
                logsDirectory: this.logsDir,
                endpoints: [
                    'GET  /health',
                    'GET  /sessions',
                    'GET  /sessions/:sessionId/log',
                    'GET  /logs',
                    'GET  /logs/system',
                    'DELETE /sessions/:sessionId',
                    'GET  /cache/keys',
                    'DELETE /cache/clear',
                    'GET  /stats',
                    'GET  /queues'
                ]
            });
        });
    }

    async setupRabbitMQ() {
        try {
            this.connection = await amqp.connect('amqp://localhost');
            this.channel = await this.connection.createChannel();
            
            // Use simpler queue declaration without complex arguments
            await this.channel.assertQueue('greenhouse_commands', { 
                durable: true
            });
            
            await this.channel.assertQueue('command_responses', { 
                durable: true
            });
            
            // Set prefetch
            await this.channel.prefetch(5);
            
            // Start single consumer (no multiple consumers)
            this.consumeCommands();
            
            this.systemLogger.info('RabbitMQ connected successfully');
            
            // Handle connection errors
            this.connection.on('error', (err) => {
                this.systemLogger.error(`RabbitMQ connection error: ${err.message}`);
            });
            
            this.connection.on('close', () => {
                this.systemLogger.warn('RabbitMQ connection closed, attempting reconnect...');
                setTimeout(() => this.setupRabbitMQ(), 5000);
            });
            
        } catch (error) {
            this.systemLogger.error(`RabbitMQ setup failed: ${error.message}`);
            setTimeout(() => this.setupRabbitMQ(), 5000);
        }
    }

    async consumeCommands() {
        try {
            this.channel.consume('greenhouse_commands', async (msg) => {
                if (!msg) return;

                let commandData;
                try {
                    commandData = JSON.parse(msg.content.toString());
                    this.systemLogger.debug(`Processing command: ${commandData.commandId}`);
                    
                    const result = await this.processCommand(commandData);
                    
                    // Send response back
                    this.channel.sendToQueue(
                        'command_responses',
                        Buffer.from(JSON.stringify(result)),
                        { persistent: true }
                    );
                    
                    this.channel.ack(msg);
                    
                } catch (error) {
                    this.commandStats.errors++;
                    this.systemLogger.error(`Command processing failed: ${error.message}`);
                    
                    // Send error response
                    const errorResponse = {
                        commandId: commandData ? commandData.commandId : 'unknown',
                        error: error.message,
                        timestamp: new Date().toISOString(),
                        sessionId: commandData ? commandData.sessionId : 'unknown'
                    };
                    
                    this.channel.sendToQueue(
                        'command_responses', 
                        Buffer.from(JSON.stringify(errorResponse))
                    );
                    
                    if (msg) {
                        this.channel.ack(msg);
                    }
                }
            }, { 
                noAck: false 
            });
            
        } catch (error) {
            this.systemLogger.error(`Consumer setup failed: ${error.message}`);
            // Restart consumer after delay
            setTimeout(() => this.consumeCommands(), 5000);
        }
    }

    async processCommand(commandData) {
        const { commandId, command, type, parameters, sessionId } = commandData;
        this.commandStats.totalProcessed++;
        
        if (!sessionId) {
            throw new Error('Session ID is required');
        }
        
        // Get or create session WITH PROPER LOCKING
        let session = this.sessions.get(sessionId);
        if (!session) {
            const logger = this.createSessionLogger(sessionId);
            session = {
                currentPath: process.cwd(),
                createdAt: new Date().toISOString(),
                lastActivity: new Date().toISOString(),
                sessionId: sessionId,
                logger: logger,
                previousPath: process.cwd(),
                commandQueue: Promise.resolve(), // Queue for session commands
                isProcessing: false
            };
            this.sessions.set(sessionId, session);
        }
        
        session.lastActivity = new Date().toISOString();
        session.logger.command(commandId, 'RECEIVED', `command: ${command}, type: ${type}`);

        // Ensure commands for the same session are processed sequentially
        session.commandQueue = session.commandQueue.then(async () => {
            return await this.executeCommandForSession(commandId, command, parameters, session);
        }).catch(error => {
            session.logger.error(`Command queue error: ${error.message}`);
            throw error;
        });

        return await session.commandQueue;
    }

    async executeCommandForSession(commandId, command, parameters, session) {
        // For stateful commands, don't use cache
        const isStatefulCommand = command === 'navigate' || command === 'change_directory' || command === 'execute_raw';
        
        if (!isStatefulCommand) {
            // Check cache for non-stateful commands
            const cacheKey = this.generateCacheKey(command, parameters, session.currentPath, session.sessionId);
            const cached = await this.redisClient.get(cacheKey);
            
            if (cached) {
                this.commandStats.cacheHits++;
                session.logger.command(commandId, 'CACHE_HIT');
                return {
                    commandId,
                    result: JSON.parse(cached),
                    cached: true,
                    sessionId: session.sessionId,
                    currentPath: session.currentPath,
                    timestamp: new Date().toISOString()
                };
            }
        }

        // Execute command
        this.commandStats.cacheMisses++;
        session.logger.command(commandId, 'EXECUTING');
        const result = await this.executeCommand(command, parameters, session);
        
        // Cache non-stateful commands
        if (!isStatefulCommand) {
            const cacheKey = this.generateCacheKey(command, parameters, session.currentPath, session.sessionId);
            const ttl = this.getTTLForCommand(command);
            await this.redisClient.setEx(cacheKey, ttl, JSON.stringify(result));
            session.logger.command(commandId, 'CACHED', `TTL: ${ttl}s`);
        }
        
        session.logger.command(commandId, 'COMPLETED');
        return {
            commandId,
            result,
            cached: false,
            sessionId: session.sessionId,
            currentPath: session.currentPath,
            timestamp: new Date().toISOString()
        };
    }

    generateCacheKey(command, parameters, currentPath, sessionId) {
        return `cmd:${sessionId}:${command}:${currentPath}:${JSON.stringify(parameters)}`;
    }

    getTTLForCommand(command) {
        const ttlConfig = {
            'list_directory': 15,     // Slightly longer TTL for better performance
            'system_status': 8,       
            'read_sensor': 5,         
            'get_current_path': 15,
            'execute_raw': 0          // No cache for raw commands
        };
        
        return ttlConfig[command] || 8;
    }

    async executeCommand(command, parameters, session) {
        try {
            switch (command) {
                case 'list_directory':
                    return await this.executeInSession(`ls -la`, parameters.path || session.currentPath, session);
                
                case 'navigate':
                    const path = parameters.path || session.currentPath;
                    const cdResult = await this.executeInSession(`cd "${path}" && pwd`, session.currentPath, session);
                    
                    if (cdResult.output && !cdResult.error) {
                        session.previousPath = session.currentPath; // Store for cd -
                        session.currentPath = cdResult.output.trim();
                    }
                    return cdResult;
                
                case 'change_directory':
                    let targetPath = parameters.path;
                    
                    // Handle cd - (go to previous directory)
                    if (targetPath === '-') {
                        if (session.previousPath) {
                            targetPath = session.previousPath;
                        } else {
                            return { error: 'No previous directory available' };
                        }
                    }
                    
                    const changeResult = await this.executeInSession(`cd "${targetPath}" && pwd`, session.currentPath, session);
                    
                    if (changeResult.output && !changeResult.error) {
                        session.previousPath = session.currentPath; // Store current as previous
                        session.currentPath = changeResult.output.trim();
                        return { 
                            output: `Directory changed to: ${session.currentPath}`,
                            newPath: session.currentPath 
                        };
                    }
                    return changeResult;
                
                case 'get_current_path':
                    return { output: session.currentPath };
                
                case 'system_status':
                    return await this.executeInSession('ps aux | head -10', session.currentPath, session);
                
                case 'read_sensor':
                    const sensorData = {
                        temperature: Math.random() * 30 + 10,
                        humidity: Math.random() * 100,
                        light: Math.random() * 1000,
                        timestamp: new Date().toISOString()
                    };
                    session.logger.info(`Sensor data generated: ${JSON.stringify(sensorData)}`);
                    return sensorData;
                
                case 'execute_raw':
                    return await this.executeInSession(parameters.raw_command, session.currentPath, session);
                
                default:
                    throw new Error(`Unknown command: ${command}`);
            }
        } catch (error) {
            session.logger.error(`Error executing command ${command}: ${error.message}`);
            throw error;
        }
    }

    executeInSession(command, workingDirectory, session) {
        return new Promise((resolve, reject) => {
            const options = {
                cwd: workingDirectory,
                shell: true,
                timeout: 15000, // Increased timeout to 15 seconds
                encoding: 'utf8',
                killSignal: 'SIGTERM'
            };

            session.logger.debug(`Executing: ${command} (cwd: ${workingDirectory})`);

            const startTime = Date.now();
            
            exec(command, options, (error, stdout, stderr) => {
                const executionTime = Date.now() - startTime;
                session.logger.debug(`Command completed in ${executionTime}ms: ${command}`);
                
                if (error) {
                    if (error.signal === 'SIGTERM') {
                        session.logger.error(`Command timeout: ${command}`);
                        reject({ 
                            error: `Command timed out after ${options.timeout}ms`,
                            code: 'TIMEOUT',
                            command: command 
                        });
                    } else {
                        session.logger.error(`Command failed: ${command} - ${error.message}`);
                        reject({ 
                            error: error.message,
                            code: error.code,
                            stderr: stderr,
                            command: command 
                        });
                    }
                } else {
                    session.logger.debug(`Command succeeded: ${command}`);
                    resolve({ 
                        output: stdout.trim(),
                        command: command,
                        executionTime: executionTime
                    });
                }
            });
        });
    }

    // Clean up old sessions periodically
    cleanupOldSessions() {
        const now = new Date();
        const MAX_SESSION_AGE = 30 * 60 * 1000; // 30 minutes
        
        for (const [sessionId, session] of this.sessions.entries()) {
            const lastActivity = new Date(session.lastActivity);
            if (now - lastActivity > MAX_SESSION_AGE) {
                session.logger.info(`Session terminated due to inactivity (${MAX_SESSION_AGE/60000} minutes)`);
                this.sessions.delete(sessionId);
                this.systemLogger.info(`Cleaned up old session: ${sessionId}`);
            }
        }
    }

    async start(port = 3000) {
        try {
            await this.redisClient.connect();
            this.systemLogger.info('Redis connected successfully');
            
            // Test command execution
            this.systemLogger.info('Testing command execution...');
            exec('echo "Command test"', { shell: true }, (error, stdout, stderr) => {
                if (error) {
                    this.systemLogger.error(`Command test failed: ${error.message}`);
                } else {
                    this.systemLogger.info(`Command test passed: ${stdout.trim()}`);
                }
            });
            
            // Start session cleanup interval (every 5 minutes)
            setInterval(() => this.cleanupOldSessions(), 5 * 60 * 1000);
            
            this.app.listen(port, () => {
                this.systemLogger.info(`Greenhouse backend running on port ${port}`);
                this.systemLogger.info(`Logs directory: ${this.logsDir}`);
                this.systemLogger.info(`API documentation available at http://localhost:${port}`);
            });
        } catch (error) {
            this.systemLogger.error(`Failed to start server: ${error.message}`);
            process.exit(1);
        }
    }
}

const backend = new GreenhouseBackend();
backend.start();