import React from 'react';
import { Navbar } from '../components/layout/Navbar';
import { Hero } from '../components/hero/Hero';
import { FeatureSummaryBar } from '../components/home/FeatureSummaryBar';
import { FeatureShowcase } from '../components/showcase/FeatureShowcase';
import { ReviewsSection } from '../components/reviews/ReviewsSection';
import { CreatorsSection } from '../components/creators/CreatorsSection';
import { ProcessSection } from '../components/home/ProcessSection';
import { RecentHistorySection } from '../components/home/RecentHistorySection';
import { FaqSection } from '../components/home/FaqSection';
import { BottomCtaSection } from '../components/home/BottomCtaSection';
import { Footer } from '../components/layout/Footer';

interface HomePageProps {
  isBackendOffline: boolean;
}

export const HomePage: React.FC<HomePageProps> = ({ isBackendOffline }) => {
  return (
    <div className="gold-page flex min-h-screen flex-col text-zinc-900 dark:text-zinc-100 transition-colors">
      <div className="gold-ambient" aria-hidden="true" />
      {/* 1. Navbar gọn gàng */}
      <Navbar isBackendOffline={isBackendOffline} />

      <main className="relative flex-1 space-y-6 sm:space-y-10">
        {/* 2. Hero hai cột */}
        <Hero />

        {/* 3. Thanh tóm tắt bốn tính năng */}
        <FeatureSummaryBar />

        {/* 4. Feature Showcase gồm bốn khối */}
        <FeatureShowcase />

        {/* TikToker/KOL được Admin xác thực và gắn với feedback thật */}
        <CreatorsSection />

        {/* 4.5. Đánh giá từ người dùng thật */}
        <ReviewsSection />

        {/* 5. Quy trình sử dụng */}
        <ProcessSection />

        {/* 6. Lịch sử gần nhất */}
        <RecentHistorySection />

        {/* 7. FAQ */}
        <FaqSection />

        {/* 8. CTA cuối trang */}
        <BottomCtaSection />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};
