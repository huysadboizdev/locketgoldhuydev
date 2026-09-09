/**
 * Trích xuất và chuẩn hóa username từ input người dùng (hỗ trợ @username, locket.cam/{user})
 */
export function extractUsername(rawInput: string): string {
  if (!rawInput) return '';
  let input = rawInput.trim();

  // Bỏ dấu @ ở đầu nếu có
  if (input.startsWith('@')) {
    input = input.substring(1);
  }

  // Nếu là URL locket.cam/...
  if (input.includes('locket.cam/')) {
    const parts = input.split('locket.cam/');
    const pathPart = parts[1]?.split('?')[0]?.split('/')[0] || '';
    input = pathPart;
  }

  return input.trim();
}

/**
 * Kiểm tra xem username có hợp lệ không
 */
export function isValidUsername(username: string): boolean {
  if (!username || username.length < 2 || username.length > 35) {
    return false;
  }
  // Chỉ chấp nhận chữ, số, dấu gạch dưới và dấu chấm
  const validRegex = /^[a-zA-Z0-9._]+$/;
  return validRegex.test(username);
}
