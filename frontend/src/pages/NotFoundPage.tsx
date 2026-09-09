import React from 'react';
import { Link } from 'react-router-dom';
import { Home } from 'lucide-react';
import { Navbar } from '../components/layout/Navbar';
import { Footer } from '../components/layout/Footer';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="gold-page flex min-h-screen flex-col text-zinc-900 dark:text-zinc-100 transition-colors">
      <Navbar />

      <main className="flex-1 flex items-center justify-center py-16 px-4 text-center">
        <div className="max-w-md space-y-4">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-3xl bg-zinc-100 dark:bg-zinc-800 text-2xl font-black text-zinc-900 dark:text-white border border-zinc-200 dark:border-zinc-700">
            404
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-white">
            Trang Không Tồn Tại
          </h1>
          <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400">
            Đường dẫn bạn truy cập không tồn tại hoặc đã được di chuyển.
          </p>
          <div className="pt-2">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-2xl bg-zinc-900 dark:bg-zinc-100 px-5 py-3 text-xs sm:text-sm font-semibold text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-white transition-colors"
            >
              <Home className="h-4 w-4" />
              <span>Quay về trang chủ</span>
            </Link>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};
