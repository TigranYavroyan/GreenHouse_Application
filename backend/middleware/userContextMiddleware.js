export default function createUserContextMiddleware({ defaultUserId, getDefaultUserId }) {
  return function userContextMiddleware(req, res, next) {
    const headerUserId = req.headers['x-user-id'];
    const tokenUserId = req.user?.id;
    const fallbackUserId = getDefaultUserId ? getDefaultUserId() : defaultUserId;
    req.contextUserId = tokenUserId || headerUserId || fallbackUserId || null;

    if (!req.contextUserId) {
      return res.status(400).json({
        error: 'User context is required',
      });
    }

    return next();
  };
}
