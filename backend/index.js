// index.js
import App from './app.js';
import SystemLogger from './logger/systemLogger.js';

const app = new App();

app.start().catch(err => {
  SystemLogger.error(`Application startup failed: ${err && err.message ? err.message : JSON.stringify(err)}`);
  process.exit(1);
});
