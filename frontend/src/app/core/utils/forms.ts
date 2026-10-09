import { HttpErrorResponse } from '@angular/common/http';

/** Field checks shared by the auth page and the change-password form; null means valid. */
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export const required = (value: string, message: string) => (value.trim() ? null : message);

export function emailError(value: string) {
  if (!value.trim()) return 'Enter your email.';
  if (value.length > 254) return 'Email cannot exceed 254 characters.';
  return EMAIL.test(value.trim()) ? null : 'Enter a valid email address.';
}

export function newPasswordError(value: string) {
  if (!value) return 'Enter a password.';
  if (value.length < 6) return 'Use at least 6 characters.';
  if (value.length > 16) return 'Use at most 16 characters.';
  return null;
}

export function confirmError(password: string, confirm: string) {
  if (!confirm) return 'Confirm your password.';
  return confirm === password ? null : "Passwords don't match.";
}

/** A readable message from a failed API call. */
export function apiErrorMessage(e: unknown): string {
  if (!(e instanceof HttpErrorResponse)) return 'Something went wrong. Please try again.';
  if (e.status === 0 || e.status >= 500) return 'Cannot reach the server. Is the backend running?';
  const detail = e.error?.detail;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors: [{loc: [..., field], msg}, ...]
  if (Array.isArray(detail) && detail.length) return `${detail[0].loc?.at(-1)}: ${detail[0].msg}`;
  return `Request failed (${e.status})`;
}
