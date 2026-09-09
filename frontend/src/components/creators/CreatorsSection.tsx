import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BadgeCheck,
  ExternalLink,
  MessageSquareQuote,
  Music2,
  Quote,
  Sparkles,
  Star,
  UsersRound,
} from 'lucide-react';
import { fetchPublicCreators } from '../../api/endpoints';
import type { PublicCreator, ReviewImage } from '../../types/api';
import { ReviewLightbox } from '../reviews/ReviewLightbox';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

const formatFollowers = (value?: number | null) => {
  if (value == null) return null;
  return new Intl.NumberFormat('vi-VN', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
};

const formatAverageRating = (value: number | null) => {
  if (value == null) return '—';
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
};

export const CreatorsSection: React.FC = () => {
  const [creators, setCreators] = useState<PublicCreator[]>([]);
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState<{ images: ReviewImage[]; index: number } | null>(null);

  const loadCreators = useCallback(async (silent = false) => {
    try {
      const response = await fetchPublicCreators();
      if (response.success) setCreators(response.creators || []);
    } catch {
      // This optional showcase must never block the rest of the landing page.
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCreators();
  }, [loadCreators]);

  useLiveRefresh(() => loadCreators(true), 10_000);

  const reviewStats = useMemo(() => {
    const ratings = creators
      .map((creator) => creator.review?.rating)
      .filter((rating): rating is number => typeof rating === 'number' && rating >= 1 && rating <= 5);

    return {
      count: ratings.length,
      average: ratings.length > 0
        ? ratings.reduce((total, rating) => total + rating, 0) / ratings.length
        : null,
    };
  }, [creators]);

  if (!loading && creators.length === 0) return null;

  return (
    <section
      id="creators"
      className="creator-community-section relative overflow-hidden py-14 sm:py-20 lg:py-24"
      aria-labelledby="creators-heading"
    >
      <div className="creator-community-glow creator-community-glow-left" aria-hidden="true" />
      <div className="creator-community-glow creator-community-glow-right" aria-hidden="true" />

      <div className="relative mx-auto max-w-[90rem] px-4 sm:px-6 lg:px-8">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)] lg:gap-14 xl:gap-20">
          <div className="mx-auto max-w-2xl text-center lg:mx-0 lg:text-left">
            <div className="inline-flex items-center gap-2 rounded-full border border-orange-300/60 bg-white/75 px-4 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-orange-700 shadow-[0_10px_35px_rgba(249,115,22,0.1)] backdrop-blur dark:border-orange-400/25 dark:bg-zinc-900/75 dark:text-orange-300 sm:text-xs">
              <Sparkles className="h-4 w-4 fill-orange-400/25" />
              Cộng đồng thật, cảm xúc thật
            </div>

            <h2
              id="creators-heading"
              className="mt-6 text-4xl font-black leading-[1.06] tracking-[-0.05em] text-zinc-950 dark:text-white sm:text-5xl xl:text-[4rem]"
            >
              Được các TikToker{' '}
              <span className="creator-heading-accent">thực sự tin tưởng</span>
            </h2>

            <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-zinc-600 dark:text-zinc-300 sm:text-base lg:mx-0">
              Mỗi hồ sơ bên cạnh đều do Admin xác thực trực tiếp. Sao, bình luận và ảnh minh chứng được đồng bộ từ feedback của chính Creator, không dùng dữ liệu mẫu.
            </p>

            {!loading && (
              <div className="mt-8 grid grid-cols-3 gap-2.5 sm:gap-4" aria-label="Thống kê TikToker xác thực">
                <div className="creator-stat-card">
                  <span className="creator-stat-icon"><UsersRound className="h-5 w-5" /></span>
                  <strong>{creators.length}</strong>
                  <span>TikToker xác thực</span>
                </div>
                <div className="creator-stat-card">
                  <span className="creator-stat-icon"><MessageSquareQuote className="h-5 w-5" /></span>
                  <strong>{reviewStats.count}</strong>
                  <span>Feedback thực tế</span>
                </div>
                <div className="creator-stat-card">
                  <span className="creator-stat-icon"><Star className="h-5 w-5 fill-current" /></span>
                  <strong>{formatAverageRating(reviewStats.average)}{reviewStats.average == null ? '' : '/5'}</strong>
                  <span>Điểm trung bình</span>
                </div>
              </div>
            )}

            <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start">
              <a
                href="#showcase-details"
                className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-orange-500 to-rose-500 px-6 text-sm font-black text-white shadow-[0_14px_34px_rgba(249,115,22,0.25)] transition hover:-translate-y-0.5 hover:shadow-[0_18px_42px_rgba(249,115,22,0.32)] focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 sm:w-auto"
              >
                Khám phá Locket Gold <ArrowRight className="h-4 w-4" />
              </a>
              <span className="max-w-xs text-center text-xs leading-5 text-zinc-500 dark:text-zinc-400 lg:text-left">
                Hồ sơ và đánh giá được xác thực từ dữ liệu hệ thống.
              </span>
            </div>
          </div>

          <div className="relative min-w-0">
            <div className="creator-doodle creator-doodle-top" aria-hidden="true"><span /><span /><span /></div>
            <div className="creator-doodle creator-doodle-bottom" aria-hidden="true"><span /><span /></div>

            {loading ? (
              <div className="flex min-h-72 items-center justify-center rounded-[2rem] border border-orange-200/70 bg-white/55 text-sm font-semibold text-zinc-500 shadow-sm backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/55 dark:text-zinc-400" role="status">
                <span className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-orange-500 border-t-transparent" />
                Đang tải hồ sơ TikToker đã xác thực…
              </div>
            ) : (
              <div className={`creator-editorial-grid ${creators.length === 1 ? 'creator-editorial-grid-single' : ''}`}>
                {creators.map((creator, index) => {
                  const followerText = formatFollowers(creator.follower_count);
                  const reviewImages = creator.review?.images || [];

                  return (
                    <article
                      key={creator.id}
                      className={`creator-story-card group ${creator.is_featured ? 'creator-story-featured' : ''}`}
                      style={{ animationDelay: `${Math.min(index, 7) * 85}ms` }}
                    >
                      <div className="creator-proof-wrap">
                        <img
                          src={creator.screenshot_url}
                          alt={`Ảnh chụp hồ sơ TikTok chính thức của @${creator.tiktok_handle}`}
                          className="creator-proof-image"
                          loading="lazy"
                          decoding="async"
                        />
                        <div className="creator-proof-shade" aria-hidden="true" />
                        <span className="creator-proof-badge"><Music2 className="h-3 w-3 text-cyan-300" /> TikToker</span>
                        {creator.is_featured && (
                          <span className="creator-featured-badge"><Sparkles className="h-3 w-3" /> Nổi bật</span>
                        )}
                      </div>

                      <div className="p-4 sm:p-5">
                        <div className="flex items-start gap-3">
                          <span className="creator-tiktok-mark"><Music2 className="h-5 w-5" /></span>
                          <div className="min-w-0 flex-1">
                            <div className="flex min-w-0 items-center gap-1.5">
                              <h3 className="truncate text-base font-black text-zinc-950 dark:text-white sm:text-lg">{creator.display_name}</h3>
                              <BadgeCheck className="h-5 w-5 shrink-0 fill-amber-400 text-amber-600" aria-label="Hồ sơ đã xác thực" />
                            </div>
                            <p className="mt-0.5 truncate text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                              @{creator.tiktok_handle}{followerText ? ` · ${followerText} follower` : ''}
                            </p>
                          </div>
                          <span className="creator-service-badge">{creator.plan_name ? 'Đã dùng dịch vụ' : 'KOL xác thực'}</span>
                        </div>

                        {creator.plan_name && (
                          <p className="mt-3 truncate text-[11px] font-bold text-orange-700 dark:text-orange-300">
                            Trải nghiệm: {creator.plan_name}
                          </p>
                        )}

                        <div className="my-4 h-px bg-zinc-200/80 dark:bg-zinc-800" />

                        {creator.review ? (
                          <div className="relative">
                            <Quote className="absolute right-0 top-0 h-7 w-7 fill-orange-300/20 text-orange-300/40" aria-hidden="true" />
                            <div className="flex items-center gap-1 pr-9" aria-label={`${creator.review.rating} trên 5 sao`}>
                              {[1, 2, 3, 4, 5].map((star) => (
                                <Star
                                  key={star}
                                  className={`h-4 w-4 ${star <= creator.review!.rating ? 'fill-amber-400 text-amber-400' : 'text-zinc-300 dark:text-zinc-700'}`}
                                />
                              ))}
                              <span className="ml-1 text-[11px] font-black text-zinc-600 dark:text-zinc-300">{creator.review.rating}/5</span>
                            </div>
                            {creator.review.content && (
                              <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                                {creator.review.content}
                              </p>
                            )}

                            {reviewImages.length > 0 && (
                              <div className="mt-3 flex gap-2">
                                {reviewImages.slice(0, 3).map((image, imageIndex) => (
                                  <button
                                    key={image.id}
                                    type="button"
                                    onClick={() => setLightbox({ images: reviewImages, index: imageIndex })}
                                    className="relative h-12 w-12 overflow-hidden rounded-xl bg-zinc-100 ring-1 ring-inset ring-zinc-200 transition hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-orange-500 dark:bg-zinc-800 dark:ring-zinc-700"
                                    aria-label={`Xem ảnh feedback ${imageIndex + 1} của ${creator.display_name}`}
                                  >
                                    <img src={image.url} alt="" className="h-full w-full object-cover" loading="lazy" decoding="async" />
                                    {imageIndex === 2 && reviewImages.length > 3 && (
                                      <span className="absolute inset-0 flex items-center justify-center bg-black/65 text-[10px] font-black text-white">+{reviewImages.length - 3}</span>
                                    )}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : (
                          <p className="text-xs leading-5 text-zinc-500 dark:text-zinc-400">
                            Hồ sơ đã được xác thực. Creator chưa gửi feedback công khai.
                          </p>
                        )}

                        <a
                          href={creator.tiktok_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-4 inline-flex items-center gap-1.5 text-xs font-black text-zinc-800 transition hover:text-cyan-600 focus:outline-none focus:ring-2 focus:ring-cyan-400 dark:text-zinc-100 dark:hover:text-cyan-300"
                        >
                          <Music2 className="h-3.5 w-3.5 text-cyan-500" /> TikTok chính chủ <ExternalLink className="h-3 w-3 opacity-60" />
                        </a>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <ReviewLightbox
        isOpen={Boolean(lightbox)}
        images={lightbox?.images || []}
        currentIndex={lightbox?.index || 0}
        onClose={() => setLightbox(null)}
        onNavigate={(index) => setLightbox((current) => current ? { ...current, index } : null)}
      />
    </section>
  );
};
