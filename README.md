# Calling Messenger Hub for Home Assistant

Custom integration gọi add-on **Calling Messenger Hub** qua REST API. Bản hiện tại dùng Telegram làm provider đầu tiên:

- gửi tin nhắn Telegram từ nhiều tài khoản;
- gửi ảnh từ URL hoặc dữ liệu ảnh kèm chú thích;
- gửi voice message bằng Edge TTS;
- gọi P2P 1:1 và phát TTS khi người nhận nghe máy;
- gọi lặp làm chuông báo động;
- theo dõi số tài khoản online và số cuộc gọi đang hoạt động.

Integration này **không chứa phần đăng nhập Telegram**. Cần cài add-on
`calling_messenger_hub` trước, sau đó nhập URL và API token của add-on.

> Chưa kiểm thử với tài khoản Telegram thật hoặc Home Assistant runtime thật.
> Gọi tự động có thể vi phạm Telegram Terms of Service; chỉ dùng tài khoản phụ
> hoặc tài khoản bạn sở hữu.

## Nâng cấp từ Telegram VoIP Notifier

Bản `2.0.1` đổi tên integration và domain:

- Integration domain: `telegram_voip` → `calling_messenger_hub`.
- Service prefix: `telegram_voip.*` → `calling_messenger_hub.*`.
- Sensor entity ID: `sensor.telegram_voip_*` → `sensor.calling_messenger_hub_*`.
- Add-on slug: `telegram_voip` → `calling_messenger_hub`.
- Dữ liệu Telegram trong `/data` của add-on giữ nguyên.

Gỡ integration cũ, cài bản mới, rồi cập nhật automation sang service prefix mới.

## Cài đặt

### HACS

1. HACS > Integrations > Custom repositories.
2. Thêm `https://github.com/trankhanhduy2929-beep/calling_messenger_hub`,
   category **Integration**.
3. Cài **Calling Messenger Hub**.
4. Restart Home Assistant.
5. Settings > Devices & services > Add integration > **Calling Messenger Hub**.
6. Nhập URL add-on, ví dụ `http://local-calling-messenger-hub:3332`, và API token.

### Thủ công

Copy thư mục `custom_components/calling_messenger_hub` vào
`/config/custom_components/calling_messenger_hub`, restart Home Assistant, rồi thêm
integration.

## Cấu hình

- **Add-on URL**: URL nội bộ của add-on, thường là
  `http://local-calling-messenger-hub:3332`. Không thêm dấu `/` ở cuối.
- **API token**: sao chép trong add-on tại **Cài đặt → API token cho custom
  integration**.

Có thể đổi URL/token sau khi cài bằng **Configure**.

## Services

`account` nhận ID tài khoản, số điện thoại quốc tế hoặc tên tài khoản trong add-on. Bỏ trống để dùng tài khoản online đầu tiên.

### `calling_messenger_hub.send_message`

```yaml
action: calling_messenger_hub.send_message
data:
  account: "+84901234567"
  to: "@username"
  message: "Cảnh báo từ Home Assistant"
```

### `calling_messenger_hub.send_tts`

```yaml
action: calling_messenger_hub.send_tts
data:
  account: "+84901234567"
  to: "@username"
  message: "Cửa chính đang mở."
  voice: "vi-VN-HoaiMyNeural"
```

### `calling_messenger_hub.send_photo`

```yaml
action: calling_messenger_hub.send_photo
data:
  account: "+84901234567"
  to: "@username"
  image: "https://example.com/camera.jpg"
  caption: "Ảnh camera cửa chính."
```

URL phải truy cập được từ Internet vì Telegram tải ảnh trực tiếp. Với ảnh nội bộ, chọn file trong Web UI.

### `calling_messenger_hub.call`

```yaml
action: calling_messenger_hub.call
data:
  account: "+84901234567"
  to: "@username"
  message: "Có người lạ trước cửa."
  ring_timeout: 45
  wait: true
```

### `calling_messenger_hub.ring`

```yaml
action: calling_messenger_hub.ring
data:
  account: "+84901234567"
  to: "@username"
  message: "Báo động. Có người ở cửa chính."
  attempts: 3
  interval: 10
```

### `calling_messenger_hub.hangup`

```yaml
action: calling_messenger_hub.hangup
data:
  call_id: "call-id"
```

Bỏ `call_id` để kết thúc mọi cuộc gọi đang hoạt động.

## Sensor

- `sensor.calling_messenger_hub_accounts_online`
- `sensor.calling_messenger_hub_active_calls`

## Ghi chú

- Tài khoản nhận phải bấm nghe máy thì TTS mới phát.
- P2P call chỉ dùng cho user Telegram, không gọi nhóm.
- Đây là provider Telegram đầu tiên của hub; dịch vụ khác sẽ được bổ sung sau.
