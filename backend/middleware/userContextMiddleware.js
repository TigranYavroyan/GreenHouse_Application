export default function createUserContextMiddleware() {
  return function userContextMiddleware(req, res, next) {
    const tokenUserId = req.user?.id;
    req.contextUserId = tokenUserId || null;

    if (!req.contextUserId) {
      return res.status(401).json({
        error: 'Unauthorized',
      });
    }

    return next();
  };
}
