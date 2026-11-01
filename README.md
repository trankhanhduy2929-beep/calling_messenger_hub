# Calling Messenger Hub for Home Assistant

Custom integration gọi add-on **Calling Messenger Hub** qua REST API. Bản `2.0.5` hỗ trợ tài khoản Telegram, Discord, Signal, LINE Official Account và SIM A7670C-LANS:

- gửi tin nhắn, ảnh và voice message bằng Edge TTS qua tài khoản đã thêm trong add-on;
- gọi P2P 1:1 Telegram và phát TTS khi người nhận nghe máy;
- gọi lặp làm chuông báo động Telegram;
- gửi chuông TTS lặp qua tài khoản Discord/Signal;
- gửi tin nhắn/ảnh qua LINE Official Account;
- gọi thoại thật qua SIM A7670C-LANS và phát TTS khi người nhận nghe máy;
- theo dõi số tài khoản online và số cuộc gọi/chuông đang hoạt động.

Integration này **không chứa phần đăng nhập**. Cần cài add-on
`calling_messenger_hub` trước, sau đó nhập URL và API token của add-on.

> Chưa kiểm thử với tài khoản Telegram, Discord, Signal, LINE hoặc mô-đun
> A7670C-LANS thật, hoặc Home Assistant runtime thật. Tự động gọi/nhắn tin có
> thể vi phạm điều khoản nền tảng và gây cước phí SIM; chỉ dùng tài khoản phụ
> và người nhận đã đồng ý.

## Nâng cấp từ Telegram VoIP Notifier

Bản `2.0.5` cập nhật mô tả service cho SIM; không đổi cấu hình.

Bản `2.0.4` cập nhật mô tả service cho LINE; không đổi cấu hình.

Bản `2.0.3` cập nhật mô tả service `ring` cho Discord/Signal; không đổi cấu hình.

Bản `2.0.2` đổi cổng mặc định của add-on sang `3030`. Nếu config entry cũ dùng cổng `3332`, integration tự cập nhật URL mặc định khi khởi động; URL tùy chỉnh cần sửa tay.

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
6. Nhập URL add-on, ví dụ `http://local-calling-messenger-hub:3030`, và API token.

### Thủ công

Copy thư mục `custom_components/calling_messenger_hub` vào
`/config/custom_components/calling_messenger_hub`, restart Home Assistant, rồi thêm
integration.

## Cấu hình

- **Add-on URL**: URL nội bộ của add-on, thường là
  `http://local-calling-messenger-hub:3030`. Không thêm dấu `/` ở cuối.
- **API token**: sao chép trong add-on tại **Cài đặt → API token cho custom
  integration**.

Có thể đổi URL/token sau khi cài bằng **Configure**.

## Services

`account` nhận ID tài khoản, số điện thoại quốc tế, tên tài khoản, ID LINE (`ln_...`) hoặc ID SIM (`sm_...`) trong add-on. Bỏ trống để dùng tài khoản Telegram online đầu tiên; SIM chỉ dùng khi chọn rõ ID. Service `call` hỗ trợ Telegram và SIM; `ring` hỗ trợ Telegram, SIM và Discord/Signal; LINE chỉ hỗ trợ `send_message` và `send_photo`. SIM không hỗ trợ gửi tin nhắn/ảnh/TTS qua API.

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

URL phải truy cập được từ Internet vì Telegram tải ảnh trực tiếp. Với ảnh nội bộ, chọn file trong Web UI. LINE chỉ nhận URL HTTPS công khai, không nhận file nội bộ hay data URI.

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

Telegram và SIM gọi thoại lặp và phát TTS khi nghe máy; SIM bỏ qua `send_message`. Discord/Signal gửi text tùy chọn một lần rồi gửi voice TTS lặp; không có phát hiện nghe máy, `ring_timeout` bị bỏ qua.

### `calling_messenger_hub.hangup`

```yaml
action: calling_messenger_hub.hangup
data:
  call_id: "call-id"
```

Bỏ `call_id` để kết thúc mọi cuộc gọi/chuông đang hoạt động.

## Sensor

- `sensor.calling_messenger_hub_accounts_online`
- `sensor.calling_messenger_hub_active_calls`

## Ghi chú

- Với Telegram, tài khoản nhận phải bấm nghe máy thì TTS mới phát; P2P call không gọi nhóm.
- Với Discord/Signal, `ring` chỉ gửi voice TTS lặp qua tin nhắn, không phải cuộc gọi thoại.
- Với LINE, dùng user/group/room ID (`U...`/`C...`/`R...`). LINE không hỗ trợ `send_tts`, `call` hoặc `ring`; ảnh phải là URL HTTPS công khai.
- Với SIM, `to` là số điện thoại. SIM chỉ gọi thoại, không nhận cuộc gọi đến, không gửi SMS/ảnh/TTS qua API; cước phí do nhà mạng tính và cần loa/mic phần cứng trên mô-đun A7670C-LANS.
