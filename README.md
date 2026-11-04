# Calling Messenger Hub for Home Assistant

Custom integration kết nối Home Assistant với add-on **Calling Messenger Hub** qua REST API. Integration dùng các tài khoản Telegram, Discord, Signal, LINE Official Account, Zalo và SIM 4G đã thêm trong add-on.

## Tính năng

- Gửi tin nhắn, ảnh và voice message bằng Edge TTS.
- Gọi P2P Telegram, gọi Zalo một chiều và gọi thoại thật qua SIM 4G; gọi thủ công, nghe máy và gửi DTMF qua SIM.
- Gọi lặp hoặc gửi voice TTS lặp làm chuông báo động.
- Kích hoạt chính sách báo động, xác nhận, đánh dấu đã xử lý hoặc hủy.
- Theo dõi tài khoản online, cuộc gọi, chuông và báo động.

Integration không chứa phần đăng nhập. Cần cài và cấu hình add-on trước.

## Yêu cầu

- Add-on **Calling Messenger Hub** đang chạy.
- API token trong add-on tại **Cài đặt → API token cho custom integration**.
- Home Assistant kết nối được tới URL nội bộ của add-on.

## Cài đặt

### HACS

1. HACS > Integrations > Custom repositories.
2. Thêm `https://github.com/trankhanhduy2929-beep/calling_messenger_hub`, category **Integration**.
3. Cài **Calling Messenger Hub**.
4. Restart Home Assistant.
5. Settings > Devices & services > Add integration > **Calling Messenger Hub**.
6. Nhập URL add-on và API token.

### Thủ công

Copy thư mục `custom_components/calling_messenger_hub` vào `/config/custom_components/calling_messenger_hub`, restart Home Assistant, rồi thêm integration.

## Cấu hình

- **Add-on URL:** thường là `http://local-calling-messenger-hub:3030`. Không thêm dấu `/` ở cuối.
- **API token:** sao chép từ add-on.
- Có thể đổi URL hoặc token sau khi cài bằng **Configure**.

## Services

`account` nhận ID tài khoản, số điện thoại quốc tế, tên tài khoản, ID Discord (`dc_...`), ID Signal (`sg_...`), ID LINE (`ln_...`), ID Zalo (`zl_...`) hoặc ID SIM (`sm_...`). Bỏ trống để add-on tự chọn tài khoản online; nên chọn rõ ID khi có nhiều dịch vụ.

### Gửi tin nhắn

```yaml
action: calling_messenger_hub.send_message
data:
  account: "+84901234567"
  to: "@username"
  message: "Cảnh báo từ Home Assistant"
```

Hỗ trợ Telegram, Discord, Signal, LINE, Zalo và SIM. Với SIM, nội dung được gửi dưới dạng SMS.

### Gửi voice TTS

```yaml
action: calling_messenger_hub.send_tts
data:
  account: "+84901234567"
  to: "@username"
  message: "Cửa chính đang mở."
  voice: "vi-VN-HoaiMyNeural"
```

Hỗ trợ Telegram, Discord, Signal và Zalo. LINE và SIM không hỗ trợ gửi TTS cục bộ.

### Gửi ảnh

```yaml
action: calling_messenger_hub.send_photo
data:
  account: "+84901234567"
  to: "@username"
  image: "https://example.com/camera.jpg"
  caption: "Ảnh camera cửa chính."
```

Hỗ trợ URL, data URL base64 hoặc file trong `/data/media` của add-on. LINE chỉ nhận URL HTTPS công khai.

### Gọi và phát TTS

```yaml
action: calling_messenger_hub.call
data:
  account: "+84901234567"
  to: "@username"
  message: "Có người lạ trước cửa."
  ring_timeout: 45
  wait: true
```

`wait: true` giữ service đến khi cuộc gọi kết thúc hoặc hết `wait_seconds`.

Với Zalo:

```yaml
action: calling_messenger_hub.call
data:
  account: "zl_1234567890"
  to: "222222222"
  message: "Có người lạ trước cửa."
  ring_timeout: 45
```

Bỏ `message` nếu chỉ muốn đổ chuông. Zalo chỉ truyền TTS một chiều, không nghe mic.

### Gọi thủ công qua SIM

```yaml
action: calling_messenger_hub.dial
data:
  account: "sm_..."
  to: "+84912345678"
  ring_timeout: 45
```

Cuộc gọi được giữ cho đến khi gọi `hangup` hoặc đầu bên kia kết thúc. `ring_timeout` là tùy chọn, từ 10 đến 180 giây.

### Nghe máy cuộc gọi SIM

```yaml
action: calling_messenger_hub.answer
data:
  account: "sm_..."
```

Dùng khi mô-đun SIM đang có cuộc gọi đến đổ chuông. Có thể truyền thêm `call_id` để gắn với bản ghi cuộc gọi cụ thể.

### Gửi DTMF trong cuộc gọi SIM

```yaml
action: calling_messenger_hub.send_dtmf
data:
  account: "sm_..."
  digits: "1#"
```

Gửi các phím `0-9`, `*`, `#`, `A-D` vào cuộc gọi đang hoạt động, ví dụ để nhập menu tổng đài.

### Chuông báo động

```yaml
action: calling_messenger_hub.ring
data:
  account: "+84901234567"
  to: "@username"
  message: "Báo động. Có người ở cửa chính."
  attempts: 3
  interval: 10
```

Telegram và SIM gọi thoại lặp. Discord và Signal gửi voice TTS lặp. Zalo và LINE không hỗ trợ chuông.

### Kết thúc cuộc gọi

```yaml
action: calling_messenger_hub.hangup
data:
  call_id: "call-id"
```

Bỏ `call_id` để kết thúc mọi cuộc gọi hoặc chuông đang hoạt động.

### Kích hoạt báo động

```yaml
action: calling_messenger_hub.trigger_alert
data:
  policy_id: "a1b2c3d4e5"
  source: "automation cua_chinh"
  dedupe_key: "cua-chinh"
```

Truyền `policy_id` hoặc `name` là tên chính xác của chính sách. `message` ghi đè lời thoại; `severity` nhận `info`, `warning` hoặc `critical`. Báo động đang chạy cùng `dedupe_key` sẽ không tạo thêm.

### Xác nhận và xử lý

```yaml
action: calling_messenger_hub.acknowledge_alert
data:
  alert_id: "f6e5d4c3b2a1"
  by: "telegram:owner"
```

- `acknowledge_alert`: xác nhận đã nhận và dừng leo thang.
- `resolve_alert`: đánh dấu đã xử lý.
- `cancel_alert`: hủy báo động và dừng cuộc gọi hoặc chuông hiện tại.

## Sensor

- `sensor.calling_messenger_hub_accounts_online`
- `sensor.calling_messenger_hub_active_calls`
- `sensor.calling_messenger_hub_alerts_active`
- `sensor.calling_messenger_hub_alerts_unacknowledged`

## Ghi chú

- Telegram chỉ gọi 1:1; người nhận phải bấm nghe máy thì TTS mới phát.
- Chưa hỗ trợ gọi đồng thời nhiều người.
- Discord dùng token tài khoản người dùng (self-bot), trái Điều khoản Discord và có thể bị khóa tài khoản. Chỉ nên dùng tài khoản phụ.
- Discord và Signal không hỗ trợ gọi thoại; `ring` chỉ gửi voice TTS lặp.
- LINE không hỗ trợ `send_tts`, `call` hoặc `ring`; ảnh phải là URL HTTPS công khai.
- Zalo không hỗ trợ `ring`; `call` chỉ đổ chuông và phát TTS một chiều.
- SIM hỗ trợ gọi, nghe máy, gửi DTMF và SMS; không gửi ảnh hoặc TTS như tin nhắn. Cước phí do nhà mạng tính.
- Âm thanh mic/loa hai chiều của SIM chưa truyền qua Home Assistant; add-on điều khiển cuộc gọi qua lệnh AT. Cần USB audio/ALSA trên host nếu muốn nghe nói trực tiếp.
- Tự động gọi/nhắn tin có thể vi phạm điều khoản nền tảng và gây cước phí; chỉ gửi đến người đã đồng ý.
