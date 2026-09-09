import React, { useState } from 'react';
import { HelpCircle, ChevronDown } from 'lucide-react';

const FAQS = [
  {
    q: 'Tôi có cần cung cấp mật khẩu Locket hoặc Apple ID không?',
    a: 'Tuyệt đối không. Hệ thống chỉ cần Username hoặc Link hồ sơ mời bạn bè công khai (locket.cam/...) để kiểm tra. Bạn không cần đăng nhập hay cung cấp bất kỳ mật khẩu nào.',
  },
  {
    q: 'Tại sao trên thiết bị iOS (iPhone/iPad) cần cài Profile DNS?',
    a: 'Profile DNS giúp định tuyến máy chủ xác thực của bên ứng dụng. Cài đặt đơn giản này giúp duy trì trạng thái ổn định trên thiết bị của bạn.',
  },
  {
    q: 'Người dùng điện thoại Android sử dụng thế nào?',
    a: 'Với Android, sau khi kích hoạt bạn chỉ cần tải file APK cài đặt tối ưu do Huy Dev cung cấp, cài đặt lên máy là toàn bộ tính năng sẽ sẵn sàng.',
  },
  {
    q: 'Nếu lỡ đăng xuất hoặc đổi điện thoại thì sao?',
    a: 'Bạn chỉ cần quay lại trang web, nhập lại username và thực hiện gửi yêu cầu kích hoạt lại qua hệ thống hàng đợi, sau đó tải lại cấu hình cho thiết bị mới.',
  },
];

export const FaqSection: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
      <div className="text-center mb-8 space-y-2">
        <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-500 dark:text-zinc-400">
          <HelpCircle className="h-3.5 w-3.5 text-zinc-500 dark:text-zinc-400" />
          <span>GIẢI ĐÁP THẮC MẮC</span>
        </div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white tracking-tight">
          Câu Hỏi Thường Gặp
        </h2>
      </div>

      <div className="space-y-3">
        {FAQS.map((item, idx) => {
          const isOpen = openIndex === idx;
          return (
            <div
              key={idx}
              className="gold-card gold-lift rounded-2xl border overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setOpenIndex(isOpen ? null : idx)}
                className="flex w-full items-center justify-between p-4 sm:p-5 text-left text-xs sm:text-sm font-semibold text-zinc-800 dark:text-zinc-100 transition-colors hover:text-zinc-950 dark:hover:text-white"
                aria-expanded={isOpen}
              >
                <span>{item.q}</span>
                <ChevronDown
                  className={`h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-200 ${
                    isOpen ? 'rotate-180 text-zinc-900 dark:text-white' : ''
                  }`}
                />
              </button>

              {isOpen && (
                <div className="px-4 pb-4 sm:px-5 sm:pb-5 text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed border-t border-zinc-100 dark:border-zinc-800/40 pt-3">
                  {item.a}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
