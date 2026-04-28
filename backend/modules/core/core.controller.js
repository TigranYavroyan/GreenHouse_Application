class CoreController {
  constructor(coreService) {
    this.coreService = coreService;
  }

  asyncHandler(res, action, statusCode = 200) {
    return Promise.resolve(action())
      .then((data) => res.status(statusCode).json(data))
      .catch((error) => this.handleError(res, error));
  }

  handleError(res, error, statusCode = 502) {
    const resolvedStatusCode =
      Number.isInteger(error?.statusCode) && error.statusCode >= 100
        ? error.statusCode
        : statusCode;

    res.status(resolvedStatusCode).json({
      error: error?.message || 'Core request failed'
    });
  }

  status = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getStatus());
  };

  getterSchema = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getGetterSchema());
  };

  executorSchema = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getExecutorSchema());
  };

  getters = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getGetters());
  };

  getterByKey = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getGetter(req.params.key));
  };

  executors = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getExecutors());
  };

  setExecutorMode = (req, res) => {
    const value = req.body?.value;
    if (value === undefined || value === null || String(value).trim() === '') {
      return this.handleError(res, new Error('Body field "value" is required'), 400);
    }

    return this.asyncHandler(res, () => this.coreService.setExecutorMode(req.params.name, value));
  };

  executorOn = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.executorOn(req.params.name));
  };

  executorOff = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.executorOff(req.params.name));
  };

  executorSet = (req, res) => {
    const value = req.body?.value;
    if (value === undefined || value === null || value === '') {
      return this.handleError(res, new Error('Body field "value" is required'), 400);
    }

    return this.asyncHandler(res, () => this.coreService.executorSet(req.params.name, value));
  };

  executorAction = (req, res) => {
    const { action, name } = req.params;
    const normalizedAction = String(action || '').trim().toLowerCase();

    if (!normalizedAction) {
      return this.handleError(res, new Error('Executor action is required'), 400);
    }

    if (normalizedAction === 'mode') {
      const value = req.body?.value;
      if (value === undefined || value === null || String(value).trim() === '') {
        return this.handleError(res, new Error('Body field "value" is required'), 400);
      }
      return this.asyncHandler(res, () => this.coreService.setExecutorMode(name, value));
    }

    if (normalizedAction === 'on') {
      return this.asyncHandler(res, () => this.coreService.executorOn(name));
    }

    if (normalizedAction === 'off') {
      return this.asyncHandler(res, () => this.coreService.executorOff(name));
    }

    if (normalizedAction === 'set') {
      const value = req.body?.value;
      if (value === undefined || value === null || String(value).trim() === '') {
        return this.handleError(res, new Error('Body field "value" is required'), 400);
      }
      return this.asyncHandler(res, () => this.coreService.executorSet(name, value));
    }

    return this.handleError(
      res,
      new Error(`Unsupported executor action: ${action}. Supported actions: mode, on, off, set`),
      400
    );
  };

  logicFull = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.getLogicFull());
  };

  logicUpload = (req, res) => {
    const payload = req.body && typeof req.body === 'object' ? req.body : {};
    return this.asyncHandler(res, () => this.coreService.uploadLogic(payload));
  };

  logicReload = (req, res) => {
    return this.asyncHandler(res, () => this.coreService.reloadLogic());
  };
}

export default CoreController;
