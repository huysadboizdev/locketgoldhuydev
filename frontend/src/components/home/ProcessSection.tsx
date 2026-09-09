import React from 'react';
import { UserCheck, Clock, ShieldCheck, ArrowRight } from 'lucide-react';

export const ProcessSection: React.FC = () => {
  const steps = [
    {
      step: '01',
      icon: UserCheck,
      title: 'Nhập Thông Tin Locket',
      description: 'Chỉ cần điền username hoặc link mời bạn bè. Tuyệt đối không yêu cầu mật khẩu hay mã OTP.',
    },
    {
      step: '02',
      icon: Clock,
      title: 'Xác Nhận & Đưa Vào Hàng Đợi',
      description: 'Hệ thống tự động đối chiếu thông tin hiển thị và xếp phiên xử lý theo cơ chế hàng đợi công bằng.',
    },
    {
      step: '03',
      icon: ShieldCheck,
      title: 'Nhận Cấu Hình Thiết Bị',
      description: 'Cài đặt Profile DNS chống thu hồi cho iOS hoặc nhận file APK tối ưu hóa cho thiết bị Android.',
    },
  ];

  return (
    <section id="process" className="mx-auto max-w-5xl px-4 sm:px-6 py-12 sm:py-16">
      <div className="text-center mb-10 sm:mb-12">
        <h2 className="text-2xl sm:text-3xl font-extrabold text-zinc-900 dark:text-white tracking-tight">
          Quy Trình 3 Bước Đơn Giản
        </h2>
        <p className="mt-2 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 max-w-md mx-auto">
          Tối giản hóa thao tác, an toàn và hoàn toàn minh bạch từng bước.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
        {steps.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="gold-card gold-lift relative rounded-3xl border p-6 flex flex-col justify-between backdrop-blur-sm"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="gold-icon flex h-11 w-11 items-center justify-center rounded-2xl border text-zinc-800 dark:text-zinc-100">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="font-mono text-xs font-bold text-zinc-400 dark:text-zinc-500">
                    {item.step}
                  </span>
                </div>
                <h3 className="text-base font-bold text-zinc-900 dark:text-white mb-2">
                  {item.title}
                </h3>
                <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  {item.description}
                </p>
              </div>

              {idx < steps.length - 1 && (
                <div className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-zinc-300 dark:text-zinc-700">
                  <ArrowRight className="h-5 w-5" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
