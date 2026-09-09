import React from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, ArrowRight, ArrowDown, Video, Crown, Palette, Camera } from 'lucide-react';
import { PhoneMockup } from '../common/PhoneMockup';
import { useAuth } from '../../hooks/useAuth';

import imgCamera from '../../assets/showcase/photo_2026-09-07_09-43-58.jpg';
import imgProfile from '../../assets/showcase/photo_2026-09-07_09-44-18.jpg';
import imgTheme from '../../assets/showcase/photo_2026-09-07_09-44-24.jpg';

export const Hero: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const handleScrollTo = (targetId: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    const elem = document.getElementById(targetId);
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const confirmedFeatures = [
    { icon: Video, label: 'Quay video Lockets' },
    { icon: Crown, label: 'Hiển thị Locket Gold' },
    { icon: Palette, label: 'Đổi biểu tượng ứng dụng' },
    { icon: Camera, label: 'Tùy biến Camera Theme' },
  ];

  return (
    <section className="relative overflow-hidden pt-8 pb-14 sm:pt-14 sm:pb-20">
      {/* Soft background ambient gradient (no heavy lag) */}
      <div className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center">
        <div className="h-72 w-72 sm:h-96 sm:w-96 rounded-full bg-amber-500/10 dark:bg-amber-400/5 blur-3xl" />
      </div>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-8 items-center">
          {/* Left Column: Product Positioning & Action */}
          <div className="gold-rise lg:col-span-6 xl:col-span-7 space-y-6 text-center lg:text-left">
            {/* Small Eyebrow Badge */}
            <div className="gold-pill inline-flex items-center gap-2 rounded-full border px-3.5 py-1 text-xs font-semibold dark:text-amber-300">
              <Sparkles className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
              <span>Giao Diện & Tính Năng Locket Gold</span>
            </div>

            {/* Clear, Prominent Headline */}
            <h1 className="text-3xl sm:text-4xl xl:text-5xl font-extrabold tracking-tight text-zinc-900 dark:text-white leading-[1.18]">
              Trải nghiệm Locket <br className="hidden sm:inline" />
              <span className="text-amber-600 dark:text-amber-400">theo cách của riêng bạn</span>
            </h1>

            {/* Concise, Honest Product Description */}
            <p className="mx-auto lg:mx-0 max-w-xl text-sm sm:text-base text-zinc-600 dark:text-zinc-300 leading-relaxed">
              Quay video, hiển thị Locket Gold, thay đổi biểu tượng ứng dụng và tùy chỉnh Camera Theme trong một trải nghiệm trực quan.
            </p>

            {/* Action Buttons */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3 w-full sm:w-auto">
              <Link
                to={isAuthenticated ? '/dashboard' : '/login?returnTo=/dashboard'}
                className="gold-primary flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl px-6 py-3.5 text-xs sm:text-sm font-bold transition-all active:scale-[0.98]"
              >
                <span>Bắt đầu nâng cấp</span>
                <ArrowRight className="h-4 w-4" />
              </Link>

              <a
                href="#features"
                onClick={handleScrollTo('features')}
                className="gold-secondary flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl border px-5 py-3.5 text-xs sm:text-sm font-semibold transition-all"
              >
                <span>Khám phá tính năng</span>
                <ArrowDown className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
              </a>
            </div>

            {/* List of 4 Confirmed Features */}
            <div className="pt-4 border-t border-zinc-200/80 dark:border-zinc-800/80">
              <p className="text-[11px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-2.5">
                4 Tính năng trọng tâm:
              </p>
              <div className="grid grid-cols-2 gap-2 sm:gap-2.5 max-w-md mx-auto lg:mx-0">
                {confirmedFeatures.map((feat, idx) => {
                  const Icon = feat.icon;
                  return (
                    <div
                      key={idx}
                      className="gold-panel flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium text-zinc-700 dark:text-zinc-300"
                    >
                      <Icon className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                      <span className="truncate">{feat.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Column: Layered Phone Mockups Showcase */}
          <div className="gold-rise gold-rise-delay-2 lg:col-span-6 xl:col-span-5 flex justify-center items-center">
            {/* Desktop Layered Display */}
            <div className="gold-float hidden sm:flex relative items-center justify-center w-full max-w-[420px] py-4">
              {/* Left Layer Phone (Camera & Video) */}
              <div className="absolute -left-6 top-8 w-[190px] xl:w-[210px] z-0 opacity-80 transition-transform duration-300 -rotate-3 scale-95">
                <PhoneMockup
                  src={imgCamera}
                  alt="Giao diện máy ảnh và quay video Locket"
                  containerClassName="w-full"
                />
              </div>

              {/* Right Layer Phone (Camera Theme) */}
              <div className="absolute -right-6 top-8 w-[190px] xl:w-[210px] z-0 opacity-80 transition-transform duration-300 rotate-3 scale-95">
                <PhoneMockup
                  src={imgTheme}
                  alt="Tùy biến Camera Theme Locket"
                  containerClassName="w-full"
                />
              </div>

              {/* Center Prominent Phone (Huy Dev Gold Profile) */}
              <div className="relative w-[230px] xl:w-[250px] z-10 shadow-2xl">
                <PhoneMockup
                  src={imgProfile}
                  alt="Hồ sơ Huy Dev hiển thị trạng thái Locket Gold"
                  priority={true}
                  containerClassName="w-full"
                  badge="Hồ sơ Huy Dev · Locket Gold"
                />
              </div>
            </div>

            {/* Mobile Compact Display (Single clean phone to preserve mobile height) */}
            <div className="gold-float sm:hidden w-full max-w-[240px] mx-auto">
              <PhoneMockup
                src={imgProfile}
                alt="Hồ sơ Huy Dev hiển thị trạng thái Locket Gold"
                priority={true}
                badge="Hồ sơ Huy Dev · Locket Gold"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
