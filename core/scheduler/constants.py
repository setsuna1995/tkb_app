"""Constants and configuration defaults for the scheduling engine."""
from __future__ import annotations

MAX_GV_BUOI = 4          # teacher cap per session (never a "full" 5-period session)
SO_LAN_THU = 6000         # max attempts (nâng từ 2000: ràng buộc "không để lẻ 1 tiết/buổi"
                          # khiến các khung có buổi chiều cần nhiều lượt thử hơn mới ra)
SO_PA_TOT = 25            # stop early once this many valid attempts are found
NGUONG_KHOA = 60          # attempts before shuffling timeslot order / discounting the "keep old" bonus
CAP_TIET_NGAY = 5         # fallback cap khi không tính được theo khung; thực tế trần mỗi
                          # ngày = tổng số ô (sáng+chiều) khung của lớp đó ngày đó (xem
                          # day_capacity trong run()), để không chặn oan khung > 5 tiết/ngày
BAT_NGHI_1_BUOI = True    # every teacher gets exactly 1 half-day-off slot/week
BAT_LIEN_MACH = True      # no gaps within a session for a class
IDLE_DAY_BONUS = 30       # điểm thưởng mềm khi đặt tiết vào ngày GV đang trống hẳn
                          # (< 100 = remaining_need*100 nên không vượt môn thiếu tiết;
                          # < 50 = phạt dàn-môn nên 1 mình nó không đảo được ưu tiên đó --
                          # nhưng khi CÙNG lúc cộng dồn với HEAVY_MORNING_BONUS trên cùng 1
                          # candidate, 30+30=60 > 50 thì cặp bonus mềm này CÓ THỂ thắng phạt
                          # dàn-môn; đây là hành vi mềm có chủ đích, không phải bug) --
                          # cố gắng không để GV trống trọn 1 ngày làm việc
HEAVY_MORNING_BONUS = 30          # điểm thưởng khi môn "Nặng" rơi vào N tiết đầu buổi sáng
                                  # (N = config.heavy_subject_priority_periods, 0 = tắt) -- cùng bậc IDLE_DAY_BONUS
AFTERNOON_MISMATCH_PENALTY = 30   # điểm phạt khi môn KHÔNG nằm trong config.afternoon_preferred_subject_ids
                                  # rơi vào buổi chiều (rỗng = tắt -- không phạt gì)
BLOCK_COMPLETE_BONUS = 40         # điểm thưởng khi tiếp tục/hoàn thành 1 khối N tiết liền kề (role_index.block_size)
                                  # -- gợi ý hiệu quả, không phải nguồn đúng đắn: _has_unpaired_block +
                                  # best-of-N mới là cơ chế đảm bảo (xem _repair_unpaired_blocks)
TEACHER_CONSECUTIVE_BONUS = 150   # điểm thưởng khi xếp liền kề tiết GV đang dạy trong cùng buổi
TEACHER_GAP_PENALTY = 250         # điểm phạt khi xếp tạo lỗ hổng (tiết trống) cho GV trong cùng buổi
TEACHER_SESSION_PAIR_BONUS = 150  # điểm thưởng khi ghép tiết thứ 2 vào cùng buổi cho GV (tránh lẻ 1 tiết)
TEACHER_SPLIT_DAY_PENALTY = 180   # điểm phạt khi tạo ngày 1 sáng + 1 chiều
TEACHER_AFTERNOON_BALANCE_BONUS = 0  # không ép rải tiết chiều trong greedy gây lẻ 1 tiết; đánh giá cân đối qua _teacher_quality_penalty
TEACHER_MANDATORY_MORNING_BONUS = 280  # điểm thưởng mạnh khi xếp tiết vào các sáng bắt buộc (T2, T5, T6)

# Buổi không được chọn làm buổi nghỉ của GV: sáng Thứ 2/5/6 (hoạt động cố định
# buổi sáng những ngày này), và chiều Thứ 5/6 (đã bị khoá hẳn khỏi TKB ở
# core/frame.py, dành cho ôn bồi dưỡng -- không phải "buổi nghỉ" GV được chọn).
FORBIDDEN_OFF_CELLS = {(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")}

FAILURE_MESSAGE = (
    "Không xếp được sau {attempts} lần thử. Nguyên nhân hay gặp:\n"
    "(1) GV HDTN (GVCN) trùng nhau giữa 2 lớp - chào cờ & SHL diễn ra đồng thời "
    "nên MỖI LỚP cần GVCN riêng;\n"
    "(2) GV_Bận cấm quá nhiều giờ của GV tải năng;\n"
    "(3) định mức SoTiet vượt khả năng khung tiết;\n"
    "(4) cấu hình nghỉ riêng của 1 GV quá chặt (off_sessions_override cao kết hợp "
    "ghim buổi/ngày nghỉ cố định) khiến các lớp GV đó dạy không đủ ô còn trống để xếp;\n"
    "(5) luật gán môn/lớp theo buổi (trang Cấu hình xếp lịch) quá chặt so với số tiết/tuần cần xếp;\n"
    "(6) môn Kép bắt buộc ghép đủ thành khối liền kề (chỉ được dư đúng 1 tiết lẻ/tuần "
    "nếu số tiết là số lẻ) -- dữ liệu quá chật khiến thuật toán không ghép được hết dù đã thử lại nhiều lần;\n"
    "(7) bật \"Môn Nặng bắt buộc xếp buổi sáng\" khiến buổi sáng quá tải, nhất là khi kết hợp "
    "với yêu cầu ghép khối môn Kép ở (6);\n"
    "(8) danh sách \"Môn bắt buộc xếp buổi sáng\" chứa quá nhiều môn khiến buổi sáng quá tải."
)
