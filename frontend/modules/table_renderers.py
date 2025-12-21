"""
Table renderers for converting different data types into table rows.
Each renderer handles a specific data structure and returns rows ready for table display.
"""
import json
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    Flatten a nested dictionary
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator for nested keys
        
    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # For lists, convert to JSON string
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def format_timestamp(timestamp: Any) -> str:
    """Format timestamp to readable string"""
    if isinstance(timestamp, str):
        try:
            # Try ISO format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(timestamp)
    elif isinstance(timestamp, (int, float)):
        try:
            dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(timestamp)
    return str(timestamp)


def format_size(size_bytes: int) -> str:
    """Format file size to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def render_health_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render health data into table format
    
    Args:
        data: Health data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Property', 'Value']
    rows = []
    
    # Flatten the data, handling nested structures
    flat_data = flatten_dict(data)
    
    # Order important fields first
    priority_fields = ['status', 'timestamp', 'redis', 'rabbitmq', 'platform', 
                       'totalSessions', 'logsDirectory']
    
    # Add priority fields first
    for field in priority_fields:
        if field in flat_data:
            value = flat_data[field]
            if field == 'timestamp':
                value = format_timestamp(value)
            rows.append([field, str(value)])
            del flat_data[field]
    
    # Add remaining fields
    for key, value in sorted(flat_data.items()):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append([key, str(value)])
    
    return columns, rows


def render_sessions_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render sessions data into table format
    
    Args:
        data: Sessions data dictionary with 'sessions' key
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Session ID', 'Session #', 'Created', 'Last Activity', 'Current Path', 'Log File']
    rows = []
    
    sessions = data.get('sessions', [])
    if isinstance(sessions, list):
        for session in sessions:
            session_id = str(session.get('id', session.get('sessionId', '')))[:8] + '...'
            session_num = str(session.get('sessionNumber', ''))
            created = format_timestamp(session.get('createdAt', session.get('created', '')))
            last_activity = format_timestamp(session.get('lastActivity', session.get('lastActivity', '')))
            current_path = str(session.get('currentPath', ''))
            log_file = str(session.get('logFile', ''))
            
            rows.append([session_id, session_num, created, last_activity, current_path, log_file])
    
    return columns, rows


def render_cache_keys_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render cache keys data into table format
    
    Args:
        data: Cache keys data dictionary with 'keys' key
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Index', 'Cache Key']
    rows = []
    
    keys = data.get('keys', [])
    if isinstance(keys, list):
        for idx, key in enumerate(keys, 1):
            rows.append([str(idx), str(key)])
    
    return columns, rows


def render_queues_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render queue status data into table format
    
    Args:
        data: Queue data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Queue Name', 'Messages', 'Consumers', 'Status']
    rows = []
    
    # Handle different queue data structures
    if 'queues' in data and isinstance(data['queues'], list):
        for queue in data['queues']:
            if isinstance(queue, dict):
                name = str(queue.get('name', ''))
                messages = str(queue.get('messages', queue.get('message_count', 'N/A')))
                consumers = str(queue.get('consumers', queue.get('consumer_count', 'N/A')))
                status = str(queue.get('status', 'active'))
                rows.append([name, messages, consumers, status])
            else:
                rows.append([str(queue), 'N/A', 'N/A', 'N/A'])
    elif isinstance(data, dict):
        # If data is a single queue object
        name = str(data.get('name', 'default'))
        messages = str(data.get('messages', data.get('message_count', 'N/A')))
        consumers = str(data.get('consumers', data.get('consumer_count', 'N/A')))
        status = str(data.get('status', 'active'))
        rows.append([name, messages, consumers, status])
    
    return columns, rows


def render_stats_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render statistics data into table format
    
    Args:
        data: Stats data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Metric', 'Value']
    rows = []
    
    # Flatten stats
    flat_data = flatten_dict(data)
    
    # Order important metrics first
    priority_metrics = ['totalCommands', 'successfulCommands', 'failedCommands', 
                       'errors', 'cacheHits', 'cacheMisses']
    
    for metric in priority_metrics:
        if metric in flat_data:
            rows.append([metric, str(flat_data[metric])])
            del flat_data[metric]
    
    # Add remaining metrics
    for key, value in sorted(flat_data.items()):
        rows.append([key, str(value)])
    
    return columns, rows


def render_logs_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render log files data into table format
    
    Args:
        data: Logs data dictionary with 'logs' key
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['File Name', 'Size', 'Modified', 'Type']
    rows = []
    
    logs = data.get('logs', [])
    if isinstance(logs, list):
        for log in logs:
            if isinstance(log, dict):
                name = str(log.get('name', ''))
                size = format_size(log.get('size', 0))
                modified = format_timestamp(log.get('modified', ''))
                log_type = str(log.get('type', 'unknown'))
                rows.append([name, size, modified, log_type])
    
    return columns, rows


def render_command_result_data(data: Dict, command: str = '', timestamp: str = '', 
                               cached: bool = False) -> Tuple[List[str], List[List[str]]]:
    """
    Render command result data into table format
    
    Args:
        data: Command result data
        command: Command name
        timestamp: Timestamp string
        cached: Whether result was cached
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Timestamp', 'Command', 'Status', 'Result', 'Cached']
    rows = []
    
    # Determine status
    error = data.get('error')
    success = data.get('success', error is None)
    status = '✅ Success' if success else '❌ Error'
    
    # Extract result
    result = data.get('result', data.get('data', {}))
    
    # Format result based on type
    if isinstance(result, dict):
        # If result has 'output', use it
        if 'output' in result:
            result_str = str(result['output'])
        # If result has 'data', format it nicely
        elif 'data' in result:
            result_data = result['data']
            if isinstance(result_data, dict):
                # For sensor data, show key values
                if 'value' in result_data:
                    result_str = f"Value: {result_data.get('value')}"
                elif 'temperature' in result_data:
                    result_str = f"Temperature: {result_data.get('temperature')}"
                else:
                    result_str = json.dumps(result_data, indent=2)[:200]  # Limit length
            else:
                result_str = str(result_data)
        else:
            # Flatten dict for display
            flat_result = flatten_dict(result)
            if len(flat_result) <= 3:
                result_str = ', '.join([f"{k}: {v}" for k, v in flat_result.items()])
            else:
                result_str = json.dumps(result, indent=2)[:200]  # Limit length
    elif isinstance(result, str):
        result_str = result[:200]  # Limit length
    else:
        result_str = str(result)[:200]  # Limit length
    
    # Handle errors
    if error:
        result_str = f"Error: {error}"
    
    cached_str = 'Yes' if cached else 'No'
    
    rows.append([timestamp, command, status, result_str, cached_str])
    
    return columns, rows


def render_fog_aggregated_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render fog aggregated data into table format
    
    Args:
        data: Fog aggregated data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Sensor Type', 'Location', 'Timeframe', 'Average', 'Min', 'Max', 'Count', 'Quality']
    rows = []
    
    data_list = data.get('data', [])
    if isinstance(data_list, list):
        for item in data_list:
            if isinstance(item, dict):
                sensor_type = str(item.get('sensorType', item.get('sensor_type', '')))
                location = str(item.get('location', ''))
                timeframe = str(item.get('timeframe', ''))
                
                # Extract data object
                data_obj = item.get('data', {})
                if isinstance(data_obj, dict):
                    avg = data_obj.get('average', 'N/A')
                    min_val = data_obj.get('min', 'N/A')
                    max_val = data_obj.get('max', 'N/A')
                    count = data_obj.get('count', 'N/A')
                    quality = data_obj.get('quality_score', 'N/A')
                else:
                    avg = min_val = max_val = count = quality = 'N/A'
                
                rows.append([sensor_type, location, timeframe, avg, min_val, max_val, count, quality])
    
    return columns, rows


def render_fog_devices_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render fog devices data into table format
    
    Args:
        data: Fog devices data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Device ID', 'Type', 'Location', 'IP Address', 'Capabilities', 'Status']
    rows = []
    
    devices = data.get('devices', [])
    if isinstance(devices, list):
        for device in devices:
            if isinstance(device, dict):
                device_id = str(device.get('device_id', device.get('deviceId', '')))
                device_type = str(device.get('device_type', device.get('type', '')))
                location = str(device.get('location', ''))
                ip_address = str(device.get('ip_address', device.get('ipAddress', '')))
                capabilities = ', '.join(device.get('capabilities', [])) if isinstance(device.get('capabilities'), list) else str(device.get('capabilities', ''))
                status = str(device.get('status', 'active'))
                rows.append([device_id, device_type, location, ip_address, capabilities, status])
    
    return columns, rows


def render_fog_anomalies_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render fog anomalies data into table format
    
    Args:
        data: Fog anomalies data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Anomaly ID', 'Sensor Type', 'Location', 'Type', 'Severity', 'Message', 'Timestamp', 'Value']
    rows = []
    
    anomalies = data.get('anomalies', [])
    if isinstance(anomalies, list):
        for anomaly in anomalies:
            if isinstance(anomaly, dict):
                anomaly_id = str(anomaly.get('anomaly_id', anomaly.get('anomalyId', '')))[:12] + '...'
                sensor_type = str(anomaly.get('sensor_type', anomaly.get('sensorType', '')))
                location = str(anomaly.get('location', ''))
                anomaly_type = str(anomaly.get('anomaly_type', anomaly.get('type', '')))
                severity = str(anomaly.get('severity', ''))
                message = str(anomaly.get('message', ''))[:50]  # Limit length
                timestamp = format_timestamp(anomaly.get('timestamp', ''))
                value = str(anomaly.get('value', 'N/A'))
                rows.append([anomaly_id, sensor_type, location, anomaly_type, severity, message, timestamp, value])
    
    return columns, rows


def render_session_log_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render session log data into table format
    
    Args:
        data: Session log data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Property', 'Value']
    rows = []
    
    # Extract key information
    session_id = data.get('sessionId', 'Unknown')
    session_number = data.get('sessionNumber', 'Unknown')
    log_file = data.get('logFile', 'Unknown')
    content = data.get('content', '')
    
    rows.append(['Session ID', str(session_id)])
    rows.append(['Session Number', str(session_number)])
    rows.append(['Log File', str(log_file)])
    
    # For log content, show first few lines or summary
    if content:
        lines = content.split('\n')
        if len(lines) > 10:
            rows.append(['Log Content', f"{len(lines)} lines (showing first 10)"])
            for i, line in enumerate(lines[:10], 1):
                rows.append([f'Line {i}', line[:100]])  # Limit line length
        else:
            rows.append(['Log Content', ''])
            for i, line in enumerate(lines, 1):
                rows.append([f'Line {i}', line[:100]])  # Limit line length
    
    return columns, rows


def render_generic_data(data: Any) -> Tuple[List[str], List[List[str]]]:
    """
    Generic renderer for unknown data structures
    
    Args:
        data: Any data structure
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = ['Property', 'Value']
    rows = []
    
    if isinstance(data, dict):
        flat_data = flatten_dict(data)
        for key, value in sorted(flat_data.items()):
            rows.append([key, str(value)])
    elif isinstance(data, list):
        # If it's a list, show index and value
        columns = ['Index', 'Value']
        for idx, item in enumerate(data, 1):
            if isinstance(item, dict):
                rows.append([str(idx), json.dumps(item)])
            else:
                rows.append([str(idx), str(item)])
    else:
        rows.append(['Data', str(data)])
    
    return columns, rows
