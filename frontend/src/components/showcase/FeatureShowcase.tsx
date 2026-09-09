import React from 'react';
import { Video, Crown, Palette, Camera, CheckCircle2, Sparkles } from 'lucide-react';
import { PhoneMockup } from '../common/PhoneMockup';

import imgCamera from '../../assets/showcase/photo_2026-09-07_09-43-58.jpg';
import imgPerks from '../../assets/showcase/photo_2026-09-07_09-44-14.jpg';
import imgProfile from '../../assets/showcase/photo_2026-09-07_09-44-18.jpg';
import imgIcons from '../../assets/showcase/photo_2026-09-07_09-44-21.jpg';
import imgThemes from '../../assets/showcase/photo_2026-09-07_09-44-24.jpg';

export const FeatureShowcase: React.FC = () => {
  return (
    <section id="showcase-details" className="mx-auto max-w-6xl px-4 sm:px-6 py-12 sm:py-16 space-y-16 sm:space-y-24">
      {/* Section Header */}
      <div className="text-center max-w-2xl mx-auto space-y-2.5">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-600/30 bg-amber-50 dark:bg-amber-950/40 px-3.5 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
          <Sparkles className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
          <span>Chi Tiết Tính Năng Sản Phẩm</span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-white">
          Trải Nghiệm Trực Quan Từng Tính Năng
        </h2>
        <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
          Ảnh chụp thực tế minh họa rõ ràng bốn nhóm tính năng Locket Gold được hỗ trợ.
        </p>
      </div>

      {/* ========================================================================= */}
      {/* BLOCK 01 — QUAY VIDEO LOCKET (Photos: 09-43-58 and 09-44-14) */}
      {/* ========================================================================= */}
      <div
        id="feature-video"
        className="gold-card gold-lift scroll-mt-24 rounded-3xl border p-6 sm:p-10 backdrop-blur-sm"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Text Content */}
          <div className="lg:col-span-6 space-y-5">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 tracking-wider">
                01 / TÍNH NĂNG
              </span>
              <span className="h-1 w-1 rounded-full bg-zinc-400 dark:bg-zinc-600" />
              <span className="inline-flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                <Video className="h-3.5 w-3.5" /> Video Lockets
              </span>
            </div>

            <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Quay & Chia Sẻ Video Lockets
            </h3>

            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">
              Ghi lại khoảnh khắc hàng ngày bằng video sống động thay vì chỉ chụp ảnh tĩnh. Gửi các đoạn video ngắn trực tiếp đến màn hình chính của bạn bè để chia sẻ cảm xúc chân thực nhất.
            </p>

            <ul className="space-y-2.5 pt-1 text-xs sm:text-sm text-zinc-700 dark:text-zinc-300">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Quay video trực tiếp ngay trên giao diện camera chính.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Gửi video tức thì tới widget của danh sách bạn bè kết nối.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Xác nhận quyền lợi Video Lockets hiển thị trong danh mục Gold.</span>
              </li>
            </ul>
          </div>

          {/* Two Complementary Uncropped Mockups */}
          <div className="lg:col-span-6 flex items-center justify-center">
            <div className="flex flex-row items-center justify-center gap-3 sm:gap-4 w-full max-w-[440px]">
              {/* Phone 1: Camera recording view */}
              <div className="w-1/2">
                <PhoneMockup
                  src={imgCamera}
                  alt="Màn hình camera quay video Locket với bạn bè"
                  badge="Giao diện Camera"
                />
              </div>

              {/* Phone 2: Gold perks list confirming Video Lockets */}
              <div className="w-1/2">
                <PhoneMockup
                  src={imgPerks}
                  alt="Danh mục quyền lợi Locket Gold xác nhận Video Lockets"
                  badge="Đặc quyền Gold"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* BLOCK 02 — HIỂN THỊ LOCKET GOLD (Photo: 09-44-18) */}
      {/* ========================================================================= */}
      <div
        id="feature-gold"
        className="gold-card gold-lift scroll-mt-24 rounded-3xl border p-6 sm:p-10 backdrop-blur-sm"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Mockup (Left on Desktop) */}
          <div className="lg:col-span-5 flex items-center justify-center order-2 lg:order-1">
            <div className="w-full max-w-[240px] sm:max-w-[260px]">
              <PhoneMockup
                src={imgProfile}
                alt="Hình ảnh minh họa trạng thái Locket Gold trên profile Huy Dev"
                badge="Hiển thị Locket Gold"
              />
            </div>
          </div>

          {/* Text Content (Right on Desktop) */}
          <div className="lg:col-span-7 space-y-5 order-1 lg:order-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 tracking-wider">
                02 / TÍNH NĂNG
              </span>
              <span className="h-1 w-1 rounded-full bg-zinc-400 dark:bg-zinc-600" />
              <span className="inline-flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                <Crown className="h-3.5 w-3.5" /> Trạng thái Gold
              </span>
            </div>

            <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Hiển Thị Locket Gold Trên Hồ Sơ
            </h3>

            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">
              Hình ảnh mang tính minh họa cho cách trạng thái Locket Gold có thể xuất hiện trên trang hồ sơ. Giao diện thực tế có thể thay đổi theo phiên bản ứng dụng.
            </p>

            <ul className="space-y-2.5 pt-1 text-xs sm:text-sm text-zinc-700 dark:text-zinc-300">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Minh họa mục Locket Gold được hiển thị trên trang hồ sơ cá nhân.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Cách hiển thị có thể thay đổi theo phiên bản ứng dụng.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Đây là hình ảnh tượng trưng, không phải dấu xác nhận chính thức.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* BLOCK 03 — ĐỔI BIỂU TƯỢNG ỨNG DỤNG (Photo: 09-44-21) */}
      {/* ========================================================================= */}
      <div
        id="feature-icons"
        className="gold-card gold-lift scroll-mt-24 rounded-3xl border p-6 sm:p-10 backdrop-blur-sm"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Text Content */}
          <div className="lg:col-span-7 space-y-5">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 tracking-wider">
                03 / TÍNH NĂNG
              </span>
              <span className="h-1 w-1 rounded-full bg-zinc-400 dark:bg-zinc-600" />
              <span className="inline-flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                <Palette className="h-3.5 w-3.5" /> App Icons
              </span>
            </div>

            <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Đổi Biểu Tượng Ứng Dụng Độc Quyền
            </h3>

            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">
              Thay đổi diện mạo icon ứng dụng Locket ngoài màn hình chính điện thoại với bộ sưu tập biểu tượng đa phong cách, từ tối giản thanh lịch đến sắc màu nổi bật.
            </p>

            <ul className="space-y-2.5 pt-1 text-xs sm:text-sm text-zinc-700 dark:text-zinc-300">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Toàn bộ danh sách mẫu icon độc quyền được mở khóa hiển thị đầy đủ.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Đổi biểu tượng nhanh chóng một chạm trực tiếp trong phần Cài đặt.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Tương thích hoàn hảo với giao diện màn hình chính của thiết bị.</span>
              </li>
            </ul>
          </div>

          {/* Mockup: Must show full icon list without cropping */}
          <div className="lg:col-span-5 flex items-center justify-center">
            <div className="w-full max-w-[240px] sm:max-w-[260px]">
              <PhoneMockup
                src={imgIcons}
                alt="Bộ sưu tập biểu tượng ứng dụng Locket Gold tùy chỉnh"
                badge="Bộ sưu tập App Icons"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* BLOCK 04 — ĐỔI CAMERA THEME (Photo: 09-44-24) */}
      {/* ========================================================================= */}
      <div
        id="feature-theme"
        className="gold-card gold-lift scroll-mt-24 rounded-3xl border p-6 sm:p-10 backdrop-blur-sm"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Mockup: Must show full theme picker without cropping (Left on Desktop) */}
          <div className="lg:col-span-5 flex items-center justify-center order-2 lg:order-1">
            <div className="w-full max-w-[240px] sm:max-w-[260px]">
              <PhoneMockup
                src={imgThemes}
                alt="Giao diện lựa chọn chủ đề Camera Theme Locket Gold"
                badge="Tùy biến Camera Theme"
              />
            </div>
          </div>

          {/* Text Content (Right on Desktop) */}
          <div className="lg:col-span-7 space-y-5 order-1 lg:order-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 tracking-wider">
                04 / TÍNH NĂNG
              </span>
              <span className="h-1 w-1 rounded-full bg-zinc-400 dark:bg-zinc-600" />
              <span className="inline-flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400 font-medium">
                <Camera className="h-3.5 w-3.5" /> Camera Theme
              </span>
            </div>

            <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Tùy Biến Chủ Đề Máy Ảnh
            </h3>

            <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">
              Tùy biến khung viền và màu sắc của màn hình máy ảnh chụp hình theo phong cách cá nhân, mang lại trải nghiệm ngắm chụp tươi mới mỗi lần mở ứng dụng.
            </p>

            <ul className="space-y-2.5 pt-1 text-xs sm:text-sm text-zinc-700 dark:text-zinc-300">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Hiển thị đầy đủ danh sách các chủ đề màu sắc máy ảnh thời thượng.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Chuyển đổi giao diện máy ảnh linh hoạt chỉ với một thao tác chọn.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <span>Khung hình chụp ảnh mang đậm dấu ấn phong cách của riêng bạn.</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
};
