import { Router } from 'express';
import CacheController from '../modules/cache/cache.controller.js';
import CacheService from '../modules/cache/cache.service.js';

export default function createCacheRouter(redisClient) {
    const router = Router();

    const service = new CacheService(redisClient);
    const controller = new CacheController(service);

    router.get('/keys', controller.getCacheKeys);
    router.delete('/clear', controller.clearCache);
    router.delete('/clear-errors', controller.clearErrorCache)

    return router;
}


