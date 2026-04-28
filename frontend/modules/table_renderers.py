"""
Table renderers for converting different data types into table rows.
Each renderer handles a specific data structure and returns rows ready for table display.
"""
import json
from datetime import datetime
from typing import List, Tuple, Dict, Any
from modules.json_prettifier import build_user_friendly_rows
from modules.localization import tr_key
from modules.localization.localization_keys import (
    TableColumns,
    Tables,
    Units,
)


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


def format_stamp_ms(stamp_ms: Any) -> str:
    """Format stamp milliseconds to local readable datetime."""
    try:
        stamp_value = int(float(stamp_ms))
    except (TypeError, ValueError):
        return str(stamp_ms)

    if stamp_value <= 0:
        return str(stamp_ms)
    return format_timestamp(stamp_value)


def format_size(size_bytes: int) -> str:
    """Format file size to human-readable format using localized unit suffixes."""
    units = (
        tr_key(Units.SIZE_B),
        tr_key(Units.SIZE_KB),
        tr_key(Units.SIZE_MB),
        tr_key(Units.SIZE_GB),
    )
    for unit in units:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} {tr_key(Units.SIZE_TB)}"


def render_health_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    """
    Render health data into table format
    
    Args:
        data: Health data dictionary
        
    Returns:
        Tuple of (columns, rows)
    """
    columns = [tr_key(TableColumns.PROPERTY), tr_key(TableColumns.VALUE)]
    rows = []
    
    flat_data = flatten_dict(data)
    
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
    columns = [
        tr_key(TableColumns.ID),
        tr_key(TableColumns.ITEM_NUMBER),
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.INFO),
        tr_key(TableColumns.PROPERTY),
        tr_key(TableColumns.VALUE),
    ]
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
    columns = [tr_key(TableColumns.ITEM_NUMBER), tr_key(TableColumns.KEY)]
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
    columns = [
        tr_key(TableColumns.NAME),
        tr_key(TableColumns.VALUE),
        tr_key(TableColumns.INFO),
        tr_key(TableColumns.STATUS),
    ]
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
    columns = [tr_key(TableColumns.PROPERTY), tr_key(TableColumns.VALUE)]
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
    columns = [
        tr_key(TableColumns.NAME),
        tr_key(TableColumns.VALUE),
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.TYPE),
    ]
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
    columns = [
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.COMMAND),
        tr_key(TableColumns.STATUS),
        tr_key(TableColumns.RESULT),
        tr_key(TableColumns.CACHED),
    ]
    rows = []
    
    error = data.get('error')
    success = data.get('success', error is None)
    status = tr_key(Tables.STATUS_SUCCESS) if success else tr_key(Tables.STATUS_FAILED)
    
    result = data.get('result', data.get('data', {}))
    click_for_details = tr_key(Tables.CLICK_FOR_DETAILS)
    
    if isinstance(result, dict):
        summary_pairs = []

        candidate_payload = result.get('data', result.get('output', result))
        if isinstance(candidate_payload, dict):
            for key, value in candidate_payload.items():
                summary_pairs.append(f"{key}: {value}")
                if len(summary_pairs) >= 3:
                    break
        else:
            summary_pairs.append(str(candidate_payload))

        if summary_pairs:
            result_str = "; ".join(summary_pairs)
            total_fields = len(candidate_payload) if isinstance(candidate_payload, dict) else 1
            if total_fields > len(summary_pairs):
                result_str = f"{result_str}; ... ({click_for_details})"
        else:
            result_str = tr_key(Tables.COMPLETED_CLICK)
    elif isinstance(result, list):
        if not result:
            result_str = tr_key(Tables.NO_ITEMS)
        else:
            preview_items = [str(item) for item in result[:3]]
            result_str = "; ".join(preview_items)
            if len(result) > 3:
                result_str = f"{result_str}; ... ({click_for_details})"
    elif isinstance(result, str):
        result_str = result[:200]
    else:
        result_str = str(result)[:200]
    
    if error:
        result_str = tr_key(Tables.ERROR_PREFIX, error=str(error))
    
    cached_str = tr_key(Tables.CACHED_YES) if cached else tr_key(Tables.CACHED_NO)
    if success and cached:
        status = tr_key(Tables.STATUS_SUCCESS_CACHED)
    
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
    columns = [
        tr_key(TableColumns.TYPE),
        tr_key(TableColumns.NAME),
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.VALUE),
        tr_key(TableColumns.PROPERTY),
        tr_key(TableColumns.INFO),
        tr_key(TableColumns.ITEM_NUMBER),
        tr_key(TableColumns.STATUS),
    ]
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
    columns = [
        tr_key(TableColumns.ID),
        tr_key(TableColumns.TYPE),
        tr_key(TableColumns.NAME),
        tr_key(TableColumns.VALUE),
        tr_key(TableColumns.PROPERTY),
        tr_key(TableColumns.STATUS),
    ]
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
    columns = [
        tr_key(TableColumns.ID),
        tr_key(TableColumns.TYPE),
        tr_key(TableColumns.NAME),
        tr_key(TableColumns.PROPERTY),
        tr_key(TableColumns.STATUS),
        tr_key(TableColumns.INFO),
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.VALUE),
    ]
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
    columns = [tr_key(TableColumns.PROPERTY), tr_key(TableColumns.VALUE)]
    rows = []
    
    unknown_label = tr_key(Tables.STATUS_UNKNOWN)
    session_id = data.get('sessionId', unknown_label)
    session_number = data.get('sessionNumber', unknown_label)
    log_file = data.get('logFile', unknown_label)
    content = data.get('content', '')
    
    rows.append([tr_key(TableColumns.ID), str(session_id)])
    rows.append([tr_key(TableColumns.ITEM_NUMBER), str(session_number)])
    rows.append([tr_key(TableColumns.NAME), str(log_file)])
    
    if content:
        lines = content.split('\n')
        if len(lines) > 10:
            rows.append([tr_key(TableColumns.INFO), str(len(lines))])
            for i, line in enumerate(lines[:10], 1):
                rows.append([str(i), line[:100]])
        else:
            rows.append([tr_key(TableColumns.INFO), ''])
            for i, line in enumerate(lines, 1):
                rows.append([str(i), line[:100]])
    
    return columns, rows


def render_core_status_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    columns = [tr_key(TableColumns.FIELD), tr_key(TableColumns.VALUE)]
    rows = []
    if isinstance(data, dict):
        status = str(data.get('status', 'unknown'))
        rows.append(['status', status])
        for key, value in sorted(data.items()):
            if key == 'status':
                continue
            rows.append([str(key), str(value)])
    return columns, rows


def render_getter_schema_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    columns = [tr_key(TableColumns.GETTER), tr_key(TableColumns.TYPE)]
    rows = []
    if isinstance(data, dict):
        for key, value in sorted(data.items(), key=lambda item: str(item[0]).lower()):
            rows.append([str(key), str(value)])
    return columns, rows


def render_executor_schema_data(data: Dict) -> Tuple[List[str], List[List[str]]]:
    columns = [tr_key(TableColumns.EXECUTOR), tr_key(TableColumns.TYPE)]
    rows = []
    if isinstance(data, dict):
        for key, value in sorted(data.items(), key=lambda item: str(item[0]).lower()):
            rows.append([str(key), str(value)])
    return columns, rows


def render_getters_snapshot_data(data: Any) -> Tuple[List[str], List[List[str]]]:
    columns = [
        tr_key(TableColumns.KEY),
        tr_key(TableColumns.VALID),
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.TYPE),
        tr_key(TableColumns.VALUE),
    ]
    rows = []

    if isinstance(data, list):
        for item in data:
            key = str(getattr(item, 'key', ''))
            valid = str(getattr(item, 'valid', False))
            stamp_ms = format_stamp_ms(getattr(item, 'stamp_ms', 0))
            typed_data = getattr(item, 'data', None)
            value_type = str(getattr(typed_data, 'value_type', 'unknown'))
            value = getattr(typed_data, 'value', None)
            rows.append([key, valid, stamp_ms, value_type, str(value)])
    elif isinstance(data, dict):
        for key, item in sorted(data.items(), key=lambda entry: str(entry[0]).lower()):
            if not isinstance(item, dict):
                rows.append([str(key), 'False', '0', 'unknown', str(item)])
                continue
            valid = str(item.get('valid', False))
            stamp_ms = format_stamp_ms(item.get('stampMs', 0))
            data_obj = item.get('data', {})
            value_type = str(data_obj.get('type', 'unknown')) if isinstance(data_obj, dict) else 'unknown'
            value = data_obj.get('value') if isinstance(data_obj, dict) else data_obj
            rows.append([str(key), valid, stamp_ms, value_type, str(value)])

    return columns, rows


def render_executors_snapshot_data(data: Any) -> Tuple[List[str], List[List[str]]]:
    columns = [
        tr_key(TableColumns.ID),
        tr_key(TableColumns.NAME),
        tr_key(TableColumns.VALID),
        tr_key(TableColumns.TIMESTAMP),
        tr_key(TableColumns.MODE),
        tr_key(TableColumns.TYPE),
        tr_key(TableColumns.VALUE),
    ]
    rows = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                executor_id = str(item.get('id', ''))
                name = str(item.get('name', ''))
                valid = str(item.get('valid', False))
                stamp_ms = format_stamp_ms(item.get('stampMs', 0))
                mode = str(item.get('mode', 'UNKNOWN'))
                data_obj = item.get('data', {})
                value_type = str(data_obj.get('type', 'unknown')) if isinstance(data_obj, dict) else 'unknown'
                value = data_obj.get('value') if isinstance(data_obj, dict) else data_obj
            else:
                executor_id = str(getattr(item, 'executor_id', ''))
                name = str(getattr(item, 'name', ''))
                valid = str(getattr(item, 'valid', False))
                stamp_ms = format_stamp_ms(getattr(item, 'stamp_ms', 0))
                mode = str(getattr(item, 'mode', 'UNKNOWN'))
                typed_data = getattr(item, 'data', None)
                value_type = str(getattr(typed_data, 'value_type', 'unknown'))
                value = getattr(typed_data, 'value', None)
            rows.append([executor_id, name, valid, stamp_ms, mode, value_type, str(value)])
    elif isinstance(data, tuple):
        for item in data:
            rows.append([str(item), '', '', '', '', '', ''])

    return columns, rows


def render_core_action_result_data(data: Any) -> Tuple[List[str], List[List[str]]]:
    columns = [tr_key(TableColumns.FIELD), tr_key(TableColumns.VALUE)]
    rows = []
    if isinstance(data, dict):
        flat_data = flatten_dict(data)
        for key, value in sorted(flat_data.items()):
            rows.append([str(key), str(value)])
    else:
        rows.append(['result', str(data)])
    return columns, rows


def render_generic_data(data: Any) -> Tuple[List[str], List[List[str]]]:
    """
    Generic renderer for unknown data structures.

    Delegates to the shared JSON prettifier so that all arbitrary JSON-like
    payloads are presented consistently in a user-friendly table form.
    """
    # No summary_text here because list/server views that call this already
    # show only the detailed table, not a short summary column.
    return build_user_friendly_rows(data, summary_text="")
