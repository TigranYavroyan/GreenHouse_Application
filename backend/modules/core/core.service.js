class CoreService {
  constructor({ greenhouseCoreClient }) {
    this.greenhouseCoreClient = greenhouseCoreClient;
  }

  getStatus() {
    return this.greenhouseCoreClient.getStatus();
  }

  getGetterSchema() {
    return this.greenhouseCoreClient.getGetterSchema();
  }

  getExecutorSchema() {
    return this.greenhouseCoreClient.getExecutorSchema();
  }

  getGetters() {
    return this.greenhouseCoreClient.getGetters();
  }

  getGetter(key) {
    return this.greenhouseCoreClient.getGetter(key);
  }

  getExecutors() {
    return this.greenhouseCoreClient.getExecutors();
  }

  setExecutorMode(name, value) {
    return this.greenhouseCoreClient.setExecutorMode(name, value);
  }

  executorOn(name) {
    return this.greenhouseCoreClient.executorOn(name);
  }

  executorOff(name) {
    return this.greenhouseCoreClient.executorOff(name);
  }

  executorSet(name, value) {
    return this.greenhouseCoreClient.executorSet(name, value);
  }
}

export default CoreService;
