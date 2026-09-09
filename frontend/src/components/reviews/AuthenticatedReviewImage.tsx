import React, { useEffect, useState } from 'react';
import { ImageOff, LoaderCircle } from 'lucide-react';
import { getAccessToken, requestTokenRefresh } from '../../api/client';

interface AuthenticatedReviewImageProps {
  src: string;
  alt: string;
  className?: string;
  loading?: 'eager' | 'lazy';
}

async function fetchImage(src: string, token: string | null): Promise<Response> {
  return fetch(src, {
    method: 'GET',
    credentials: 'same-origin',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}

export const AuthenticatedReviewImage: React.FC<AuthenticatedReviewImageProps> = ({
  src,
  alt,
  className = '',
  loading = 'lazy',
}) => {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let createdUrl: string | null = null;

    const load = async () => {
      setFailed(false);
      setObjectUrl(null);

      try {
        let response = await fetchImage(src, getAccessToken());

        if (response.status === 401) {
          const refreshedToken = await requestTokenRefresh();
          if (refreshedToken) {
            response = await fetchImage(src, refreshedToken);
          }
        }

        if (!response.ok) {
          throw new Error(`Image request failed with status ${response.status}`);
        }

        const contentType = response.headers.get('content-type') || '';
        if (!contentType.startsWith('image/')) {
          throw new Error('Response is not an image');
        }

        const blob = await response.blob();
        const nextUrl = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
        createdUrl = nextUrl;
        setObjectUrl(nextUrl);
      } catch {
        if (!cancelled) {
          setFailed(true);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [src]);

  if (failed) {
    return (
      <span className="flex h-full w-full items-center justify-center bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-600" role="img" aria-label={`${alt} không tải được`}>
        <ImageOff className="h-5 w-5" />
      </span>
    );
  }

  if (!objectUrl) {
    return (
      <span className="flex h-full w-full items-center justify-center bg-zinc-100 text-amber-500 dark:bg-zinc-900" aria-hidden="true">
        <LoaderCircle className="h-5 w-5 animate-spin" />
      </span>
    );
  }

  return <img src={objectUrl} alt={alt} className={className} loading={loading} />;
};
