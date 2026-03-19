import crypto from 'crypto';
import cron from 'node-cron';

class SchedulesRuntime {
  constructor({ schedulesRepository, rabbitClient, logger }) {
    this.schedulesRepository = schedulesRepository;
    this.rabbitClient = rabbitClient;
    this.logger = logger;
    this.jobs = new Map();
    this.started = false;
  }

  async start() {
    await this.reloadAll();
    this.started = true;
  }

  stop() {
    for (const job of this.jobs.values()) {
      try {
        job.stop();
        if (typeof job.destroy === 'function') {
          job.destroy();
        }
      } catch (error) {
        this.logger.warn(`Failed to stop schedule job: ${error.message}`);
      }
    }
    this.jobs.clear();
    this.started = false;
  }

  async reloadAll() {
    this.stop();
    const enabledSchedules = await this.schedulesRepository.findAllEnabled();

    for (const schedule of enabledSchedules) {
      this._registerJob(schedule);
    }

    this.logger.info(`Schedules runtime loaded ${enabledSchedules.length} enabled schedule(s)`);
  }

  async upsert(schedule) {
    if (!this.started) return;
    if (!schedule) return;

    this._unregisterJob(schedule.id);
    if (!schedule.enabled) return;
    this._registerJob(schedule);
  }

  async remove(scheduleId) {
    if (!this.started) return;
    this._unregisterJob(scheduleId);
  }

  _registerJob(schedule) {
    const cronExpression = String(schedule.cronExpression || '').trim();
    if (!cron.validate(cronExpression)) {
      this.logger.warn(`Skipping invalid cron schedule ${schedule.id}: ${cronExpression}`);
      return;
    }

    const scheduleId = schedule.id;
    const job = cron.schedule(cronExpression, async () => {
      await this._dispatchSchedule(scheduleId);
    });
    this.jobs.set(scheduleId, job);
  }

  _unregisterJob(scheduleId) {
    const existing = this.jobs.get(scheduleId);
    if (!existing) return;

    existing.stop();
    if (typeof existing.destroy === 'function') {
      existing.destroy();
    }
    this.jobs.delete(scheduleId);
  }

  async _dispatchSchedule(scheduleId) {
    const schedule = await this.schedulesRepository.findEnabledById(scheduleId);
    if (!schedule) {
      this._unregisterJob(scheduleId);
      return;
    }

    const commandId = crypto.randomUUID();
    const fallbackSessionId = `schedule:${schedule.device?.userId || 'default'}:${schedule.id}`;
    const metadata = schedule.metadata || {};
    const scheduleMode = this._resolveScheduleMode(metadata);
    const payload = schedule.payload || {};
    const parameters =
      payload && typeof payload === 'object' && payload.parameters && typeof payload.parameters === 'object'
        ? payload.parameters
        : payload;
    const envelope = {
      commandId,
      command: schedule.action,
      type: 'user',
      parameters,
      sessionId: metadata.sessionId || fallbackSessionId,
      source: 'scheduler',
      scheduleId: schedule.id,
    };

    try {
      const queued = this.rabbitClient.sendToQueue(
        'greenhouse_commands',
        Buffer.from(JSON.stringify(envelope)),
        { persistent: true }
      );
      if (!queued) {
        throw new Error('Queue publish was buffered by RabbitMQ channel');
      }

      await this._markDispatchSuccess(schedule.id, commandId, scheduleMode);
      if (scheduleMode === 'one_time') {
        this._unregisterJob(scheduleId);
      }
      this.logger.info(`Dispatched schedule ${schedule.id} -> command ${commandId} (mode=${scheduleMode})`);
    } catch (error) {
      await this._markDispatchFailure(schedule.id, scheduleMode, error);
      if (scheduleMode === 'one_time') {
        this._unregisterJob(scheduleId);
      }
      this.logger.error(`Failed to dispatch schedule ${schedule.id} (mode=${scheduleMode}): ${error.message}`);
    }
  }

  _resolveScheduleMode(metadata = {}) {
    const normalized = String(metadata?.scheduleMode || metadata?.mode || '').trim().toLowerCase();
    if (!normalized || normalized === 'one-time' || normalized === 'one_time' || normalized === 'onetime') {
      return 'one_time';
    }
    if (normalized === 'recurring') {
      return 'recurring';
    }
    return 'one_time';
  }

  async _markDispatchSuccess(scheduleId, commandId, scheduleMode) {
    const nowIso = new Date().toISOString();
    const metadataPatch = {
      lastDispatchedAt: nowIso,
      lastDispatchStatus: 'completed',
      lastDispatchError: '',
      lastCommandId: commandId,
      scheduleStatus: scheduleMode === 'one_time' ? 'completed' : 'pending',
      ...(scheduleMode === 'one_time' ? { completedAt: nowIso } : { lastCompletedAt: nowIso }),
    };
    if (scheduleMode === 'one_time') {
      await this.schedulesRepository.finalizeOneTimeById(scheduleId, metadataPatch);
      return;
    }
    await this.schedulesRepository.updateDispatchMetadataById(scheduleId, metadataPatch);
  }

  async _markDispatchFailure(scheduleId, scheduleMode, error) {
    const nowIso = new Date().toISOString();
    const metadataPatch = {
      lastDispatchedAt: nowIso,
      lastDispatchStatus: 'failed',
      lastDispatchError: error.message,
      scheduleStatus: scheduleMode === 'one_time' ? 'not_done' : 'pending',
      ...(scheduleMode === 'one_time' ? { failedAt: nowIso } : { lastFailedAt: nowIso }),
    };
    if (scheduleMode === 'one_time') {
      await this.schedulesRepository.finalizeOneTimeById(scheduleId, metadataPatch);
      return;
    }
    await this.schedulesRepository.updateDispatchMetadataById(scheduleId, metadataPatch);
  }
}

export default SchedulesRuntime;
