/**
 * Sanitize open redirect parameter `returnTo` or `next`.
 * Must be a safe internal relative path starting with `/`,
 * rejecting protocol-relative URLs (`//`), backslashes (`\`), or external schemes.
 */
export function sanitizeReturnTo(raw: string | null | undefined): string {
  if (!raw) {
    return '/';
  }
  let trimmed = raw.trim();
  if (trimmed.startsWith('#')) {
    trimmed = '/' + trimmed;
  }
  // Must start with single slash, not followed by another slash or backslash
  if (trimmed.startsWith('/') && !trimmed.startsWith('//') && !trimmed.startsWith('/\\') && !trimmed.includes('\\')) {
    // Disallow javascript: or data: even if encoded
    if (!trimmed.toLowerCase().includes('javascript:') && !trimmed.toLowerCase().includes('data:')) {
      return trimmed;
    }
  }
  return '/';
}

/**
 * Authentication in this app always enters the private application. Preserve
 * only destinations inside the dashboard and never send an authenticated user
 * back to the public landing page.
 */
export function getDashboardReturnTo(raw: string | null | undefined): string {
  const safePath = sanitizeReturnTo(raw);
  return safePath === '/dashboard' || safePath.startsWith('/dashboard?') || safePath.startsWith('/dashboard/')
    ? safePath
    : '/dashboard';
}

/**
 * Directs post-login redirection based on user role.
 * - For admin: always directs into /admin (preserving only an /admin returnTo).
 * - For user: directs to /dashboard (or returnTo if within /dashboard).
 */
export function getPostLoginReturnTo(role: string | null | undefined, raw: string | null | undefined): string {
  const safePath = sanitizeReturnTo(raw);
  if (role === 'admin') {
    if (safePath === '/admin' || safePath.startsWith('/admin?') || safePath.startsWith('/admin/')) {
      return safePath;
    }
    return '/admin';
  }
  return getDashboardReturnTo(raw);
}
