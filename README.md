# Calling Messenger Hub for Home Assistant

Custom integration kết nối Home Assistant với add-on **Calling Messenger Hub** qua REST API. Integration dùng các tài khoản Telegram, Discord, Signal, LINE Official Account, Zalo và SIM 4G đã thêm trong add-on.

## Tính năng

- Gửi tin nhắn, ảnh và voice message bằng Edge TTS.
- Gọi P2P Telegram, gọi Zalo một chiều và gọi thoại thật qua SIM 4G.
- Gọi lặp hoặc gửi voice TTS lặp làm chuông báo động.
- Kích hoạt chính sách báo động, xác nhận, đánh dấu đã xử lý hoặc hủy.
- Theo dõi tài khoản online, cuộc gọi, chuông, báo động, license, MQTT và sức khỏe SIM.
- Nhận sự kiện realtime qua SSE, gần như ngay lập tức; tự kết nối lại khi mất luồng và vẫn có polling dự phòng.
- Cảm biến sức khỏe luồng SSE: trạng thái kết nối, sự kiện gần nhất, số lần kết nối lại và nút khởi động lại luồng.
- Mỗi tài khoản có binary_sensor online riêng; mỗi SIM có thêm cảm biến sóng, nhà mạng, số dư và hạn dùng.
- Gửi thông báo qua `notify.calling_messenger_hub` và nhận event cuộc gọi, chuông, báo động, SMS/OTP và tài khoản.
- Thông báo Home Assistant có nút **Đã xử lý**, **Tắt chuông** và **Mở** dashboard.
- Device trigger theo từng loại sự kiện để dựng automation trực tiếp trong giao diện Home Assistant.

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

### Tùy chọn thông báo

Mở **Configure** để cấu hình:

- **Notification service:** dịch vụ notify của Home Assistant, ví dụ `notify.mobile_app_dien_thoai`.
- **Notification event types:** các loại sự kiện cần gửi thông báo. Mặc định là báo động, OTP và SMS.
- **Notification open URL:** dashboard hoặc trang web mở khi bấm **Mở** trên thông báo.

Thông báo báo động có thêm nút **Đã xử lý** và **Tắt chuông** khi sự kiện có cuộc gọi hoặc chuông. Bấm **Đã xử lý** sẽ resolve báo động; **Tắt chuông** kết thúc cuộc gọi hoặc chuông đang chạy.

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

## Entity và notify

- `sensor`: tài khoản online, cuộc gọi, báo động đang chạy và chưa xác nhận; sự kiện SSE gần nhất và số lần kết nối lại; mỗi SIM có thêm sóng, nhà mạng, số dư và hạn dùng.
- `binary_sensor`: kết nối API, kết nối luồng SSE, license, MQTT, sự cố SIM, bản cập nhật và trạng thái online của từng tài khoản.
- `button`: làm mới trạng thái, khởi động lại luồng SSE và kiểm tra cập nhật.
- `switch.calling_messenger_hub_mqtt_bridge`: bật/tắt cầu nối MQTT.
- `event.calling_messenger_hub_activity`: cuộc gọi, chuông, báo động, tin nhắn, SMS/OTP, tài khoản, automation và sự kiện khác. SMS/OTP không chứa nội dung hoặc mã.
- Entity của tài khoản được thêm hoặc gỡ tự động khi danh sách tài khoản trong add-on thay đổi.

Gửi notify:

```yaml
action: notify.calling_messenger_hub
data:
  title: "Home Assistant"
  message: "Cửa chính đang mở."
  target:
    - "@username"
  data:
    account: "+84901234567"
```

`target` hoặc `data.to` là người nhận. `data` hỗ trợ thêm `account`, `parse_mode` và `silent`.

## Device trigger

Mỗi loại sự kiện SSE có device trigger trên thiết bị **Calling Messenger Hub**. Trong automation, chọn **Add trigger → Device → Calling Messenger Hub** rồi chọn loại sự kiện như `sms`, `call`, `alert`, `otp` hoặc `ring`. Trigger truyền dữ liệu sự kiện trong biến `trigger.event`.

## Ghi chú

- Telegram chỉ gọi 1:1; người nhận phải bấm nghe máy thì TTS mới phát.
- Chưa hỗ trợ gọi đồng thời nhiều người.
- Discord dùng token tài khoản người dùng (self-bot), trái Điều khoản Discord và có thể bị khóa tài khoản. Chỉ nên dùng tài khoản phụ.
- Discord và Signal không hỗ trợ gọi thoại; `ring` chỉ gửi voice TTS lặp.
- LINE không hỗ trợ `send_tts`, `call` hoặc `ring`; ảnh phải là URL HTTPS công khai.
- Zalo không hỗ trợ `ring`; `call` chỉ đổ chuông và phát TTS một chiều.
- SIM hỗ trợ gọi cảnh báo, nghe máy, gửi DTMF và SMS trong add-on; integration chỉ gửi tin, gọi cảnh báo và chuông. Cước phí do nhà mạng tính.
- Âm thanh mic/loa hai chiều của SIM chưa truyền qua Home Assistant; add-on điều khiển cuộc gọi qua lệnh AT. Cần USB audio/ALSA trên host nếu muốn nghe nói trực tiếp.
- Tự động gọi/nhắn tin có thể vi phạm điều khoản nền tảng và gây cước phí; chỉ gửi đến người đã đồng ý.
