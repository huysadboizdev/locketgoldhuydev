import React from 'react';
import { Video, Crown, Palette, Camera, ArrowUpRight } from 'lucide-react';

export const FeatureSummaryBar: React.FC = () => {
  const handleScrollTo = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    const elem = document.getElementById(id);
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const features = [
    {
      id: 'feature-video',
      icon: Video,
      num: '01',
      title: 'Quay Video Lockets',
      desc: 'Quay và chia sẻ video trực tiếp tới widget bạn bè.',
    },
    {
      id: 'feature-gold',
      icon: Crown,
      num: '02',
      title: 'Hiển Thị Locket Gold',
      desc: 'Minh họa trạng thái Locket Gold trên trang hồ sơ.',
    },
    {
      id: 'feature-icons',
      icon: Palette,
      num: '03',
      title: 'Đổi Biểu Tượng Ứng Dụng',
      desc: 'Bộ icon độc quyền làm mới giao diện màn hình chính.',
    },
    {
      id: 'feature-theme',
      icon: Camera,
      num: '04',
      title: 'Đổi Camera Theme',
      desc: 'Tùy biến bảng màu và phong cách giao diện máy ảnh.',
    },
  ];

  return (
    <section id="features" className="mx-auto max-w-6xl px-4 sm:px-6 py-6 sm:py-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {features.map((item, index) => {
          const Icon = item.icon;
          return (
            <a
              key={item.id}
              href={`#${item.id}`}
              onClick={handleScrollTo(item.id)}
              className={`gold-card gold-lift gold-rise group relative rounded-2xl sm:rounded-3xl border p-4 sm:p-5 flex flex-col justify-between gold-rise-delay-${Math.min(index, 3)}`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="gold-icon flex h-9 w-9 items-center justify-center rounded-xl border text-zinc-800 dark:text-zinc-100 group-hover:text-amber-700 dark:group-hover:text-amber-400 transition-colors">
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="font-mono text-[10px] font-bold text-zinc-400 dark:text-zinc-500">
                    {item.num}
                  </span>
                </div>

                <h3 className="text-xs sm:text-sm font-bold text-zinc-900 dark:text-white group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors flex items-center gap-1">
                  <span>{item.title}</span>
                  <ArrowUpRight className="h-3 w-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-amber-500" />
                </h3>

                <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400 leading-relaxed">
                  {item.desc}
                </p>
              </div>
            </a>
          );
        })}
      </div>
    </section>
  );
};
